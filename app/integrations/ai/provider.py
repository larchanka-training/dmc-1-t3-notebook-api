from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import (
        BotoCoreError,
        ClientError,
        ConnectTimeoutError,
        EndpointConnectionError,
        ReadTimeoutError,
    )
except ModuleNotFoundError:  # pragma: no cover - depends on local env bootstrap
    boto3 = None
    Config = None

    class BotoCoreError(Exception):
        pass

    class ClientError(Exception):
        def __init__(self, error_response: dict[str, Any] | None = None) -> None:
            self.response = error_response or {}
            super().__init__(str(self.response))

    class ConnectTimeoutError(TimeoutError):
        pass

    class ReadTimeoutError(TimeoutError):
        pass

    class EndpointConnectionError(Exception):
        def __init__(self, endpoint_url: str) -> None:
            self.endpoint_url = endpoint_url
            super().__init__(endpoint_url)


@dataclass(slots=True)
class AiProviderGenerateRequest:
    request_id: str
    notebook_id: str
    source_block_id: str
    mode: str
    prompt: str
    context: dict[str, Any]
    insertion_strategy: str
    attempt: int = 0
    repair_feedback: str | None = None
    previous_response_content: str | None = None


@dataclass(slots=True)
class AiProviderGenerateResponse:
    content: str
    provider_name: str
    model: str


class AiProviderError(Exception):
    """Base class for provider-facing failures."""


class AiProviderUnavailableError(AiProviderError):
    """Raised when the provider or transport is unavailable."""


class AiProviderTimeoutError(AiProviderError):
    """Raised when the provider exceeds the backend timeout budget."""


class AiProviderInvalidResponseError(AiProviderError):
    """Raised when the provider response is malformed or unusable."""


class AiGenerationGateway:
    async def generate(
        self, request: AiProviderGenerateRequest
    ) -> AiProviderGenerateResponse:
        raise NotImplementedError


class UnavailableAiGenerationGateway(AiGenerationGateway):
    """Placeholder boundary for the future Bedrock-backed implementation."""

    def __init__(
        self,
        *,
        provider_name: str,
        model: str,
        message: str = "The AI provider is temporarily unavailable. Try again.",
    ) -> None:
        self.provider_name = provider_name
        self.model = model
        self.message = message

    async def generate(
        self, request: AiProviderGenerateRequest
    ) -> AiProviderGenerateResponse:
        raise AiProviderUnavailableError(self.message)


def build_bedrock_request_text(request: AiProviderGenerateRequest) -> str:
    parts = [
        "Generate JavaScript code for the notebook task below.",
        "Return only plain JavaScript code.",
        "Do not include markdown fences, explanations, or prose.",
        "Return one complete, syntactically valid JavaScript snippet.",
        "Do not repeat the prompt or context in the output.",
        "If the task is underspecified, return the smallest valid implementation that satisfies it.",
        "Before responding, verify that parentheses, braces, brackets, quotes, and template literals are balanced.",
        f"Request ID: {request.request_id}",
        f"Mode: {request.mode}",
        f"Insertion strategy: {request.insertion_strategy}",
        f"Prompt:\n{request.prompt}",
        "Context JSON:",
        json.dumps(request.context, ensure_ascii=True, sort_keys=True),
    ]

    if request.attempt > 0:
        parts.append(f"Repair attempt: {request.attempt}")
    if request.repair_feedback:
        parts.append(f"Repair feedback:\n{request.repair_feedback}")
    if request.previous_response_content:
        parts.append(
            "Previous provider response to repair:\n"
            f"{request.previous_response_content}"
        )

    return "\n\n".join(parts)


class BedrockAiGenerationGateway(AiGenerationGateway):
    def __init__(
        self,
        *,
        region: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        provider_name: str = "bedrock",
        client: Any | None = None,
    ) -> None:
        self.region = region
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.provider_name = provider_name
        if client is not None:
            self.client = client
            return

        if boto3 is None or Config is None:
            raise RuntimeError("boto3 with bedrock-runtime support is not installed.")

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=timeout_seconds,
                read_timeout=timeout_seconds,
                retries={"max_attempts": max_retries, "mode": "standard"},
            ),
        )

    async def generate(
        self, request: AiProviderGenerateRequest
    ) -> AiProviderGenerateResponse:
        try:
            response = await asyncio.to_thread(
                self.client.converse,
                modelId=self.model,
                system=[
                    {
                        "text": (
                            "You generate JavaScript for a notebook backend workflow. "
                            "Return only one complete, syntactically valid JavaScript snippet "
                            "with no markdown fences, no explanations, and no surrounding prose."
                        )
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": build_bedrock_request_text(request)}],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0,
                },
            )
        except (ConnectTimeoutError, ReadTimeoutError, TimeoutError) as exc:
            raise AiProviderTimeoutError(
                "The AI provider did not respond in time."
            ) from exc
        except EndpointConnectionError as exc:
            raise AiProviderUnavailableError(
                "The AI provider endpoint is unreachable."
            ) from exc
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in {"ModelTimeoutException", "RequestTimeout"}:
                raise AiProviderTimeoutError(
                    "The AI provider did not respond in time."
                ) from exc
            raise AiProviderUnavailableError(
                "The AI provider request failed."
            ) from exc
        except BotoCoreError as exc:
            raise AiProviderUnavailableError(
                "The AI provider transport failed."
            ) from exc

        content = self._extract_text_content(response)
        return AiProviderGenerateResponse(
            content=content,
            provider_name=self.provider_name,
            model=self.model,
        )

    def _extract_text_content(self, response: dict[str, Any]) -> str:
        try:
            output = response["output"]
            message = output["message"]
            content_blocks = message["content"]
        except (KeyError, TypeError) as exc:
            raise AiProviderInvalidResponseError(
                "The AI provider response payload was malformed."
            ) from exc

        if not isinstance(content_blocks, list):
            raise AiProviderInvalidResponseError(
                "The AI provider response content was malformed."
            )

        text_parts: list[str] = []
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str):
                text_parts.append(text)

        if not text_parts:
            raise AiProviderInvalidResponseError(
                "The AI provider response did not contain text content."
            )

        return "".join(text_parts)
