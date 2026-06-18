from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
