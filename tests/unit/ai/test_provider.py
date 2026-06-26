from __future__ import annotations

from app.core.config import Settings
from app.features.ai import dependencies as ai_dependencies
from app.integrations.ai import (
    AiProviderGenerateRequest,
    AiProviderInvalidResponseError,
    AiProviderTimeoutError,
    AiProviderUnavailableError,
    BedrockAiGenerationGateway,
    UnavailableAiGenerationGateway,
)
from app.integrations.ai.provider import EndpointConnectionError


class FakeBedrockClient:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def _request(**overrides) -> AiProviderGenerateRequest:
    payload = {
        "request_id": "air_test_001",
        "notebook_id": "notebook-1",
        "source_block_id": "blk_text_1",
        "mode": "generate",
        "prompt": "Write JavaScript code that parses totals.",
        "context": {
            "language": "javascript",
            "scope": "this",
            "sourceText": "Parse totals from CSV input.",
        },
        "insertion_strategy": "next-empty-or-new-after-source",
    }
    payload.update(overrides)
    return AiProviderGenerateRequest(**payload)


async def test_bedrock_gateway_maps_successful_response() -> None:
    client = FakeBedrockClient(
        response={
            "output": {
                "message": {
                    "content": [
                        {"text": "function parseTotals() {\n  return [];\n}"},
                    ]
                }
            }
        }
    )
    gateway = BedrockAiGenerationGateway(
        region="us-east-1",
        model="deepseek.v3.2",
        timeout_seconds=12.5,
        max_retries=2,
        client=client,
    )

    response = await gateway.generate(_request())

    assert response.provider_name == "bedrock"
    assert response.model == "deepseek.v3.2"
    assert response.content == "function parseTotals() {\n  return [];\n}"
    assert client.calls[0]["modelId"] == "deepseek.v3.2"
    assert client.calls[0]["inferenceConfig"] == {
        "maxTokens": 4096,
        "temperature": 0,
    }


async def test_bedrock_gateway_includes_repair_feedback_in_request() -> None:
    client = FakeBedrockClient(
        response={
            "output": {
                "message": {
                    "content": [
                        {"text": "function repaired() {\n  return 1;\n}"},
                    ]
                }
            }
        }
    )
    gateway = BedrockAiGenerationGateway(
        region="us-east-1",
        model="deepseek.v3.2",
        timeout_seconds=12.5,
        max_retries=2,
        client=client,
    )

    await gateway.generate(
        _request(
            attempt=1,
            repair_feedback="Previous response had syntax errors.",
            previous_response_content="function broken( {",
        )
    )

    user_message = client.calls[0]["messages"][0]["content"][0]["text"]
    assert "Repair attempt: 1" in user_message
    assert "Previous response had syntax errors." in user_message
    assert "function broken( {" in user_message


async def test_bedrock_gateway_maps_timeout_errors() -> None:
    gateway = BedrockAiGenerationGateway(
        region="us-east-1",
        model="deepseek.v3.2",
        timeout_seconds=12.5,
        max_retries=2,
        client=FakeBedrockClient(error=TimeoutError("slow")),
    )

    try:
        await gateway.generate(_request())
    except AiProviderTimeoutError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected AiProviderTimeoutError")


async def test_bedrock_gateway_maps_unavailable_errors() -> None:
    gateway = BedrockAiGenerationGateway(
        region="us-east-1",
        model="deepseek.v3.2",
        timeout_seconds=12.5,
        max_retries=2,
        client=FakeBedrockClient(
            error=EndpointConnectionError(endpoint_url="https://bedrock-runtime")
        ),
    )

    try:
        await gateway.generate(_request())
    except AiProviderUnavailableError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected AiProviderUnavailableError")


async def test_bedrock_gateway_maps_malformed_response() -> None:
    gateway = BedrockAiGenerationGateway(
        region="us-east-1",
        model="deepseek.v3.2",
        timeout_seconds=12.5,
        max_retries=2,
        client=FakeBedrockClient(response={"unexpected": "payload"}),
    )

    try:
        await gateway.generate(_request())
    except AiProviderInvalidResponseError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected AiProviderInvalidResponseError")


def test_ai_gateway_dependency_returns_unavailable_when_runtime_is_disabled() -> None:
    settings = Settings(
        AI_PROVIDER_ENABLED=False,
        AI_PROVIDER_MODEL="deepseek.v3.2",
        AI_BEDROCK_REGION="us-east-1",
    )

    gateway = ai_dependencies.get_ai_generation_gateway(settings=settings)

    assert isinstance(gateway, UnavailableAiGenerationGateway)
    assert ai_dependencies.get_ai_runtime_status(settings) == {
        "provider": "bedrock",
        "configured": False,
        "ready": False,
        "reason": "disabled",
        "missing_fields": ["AI_PROVIDER_ENABLED"],
    }


def test_ai_gateway_dependency_returns_bedrock_gateway_when_runtime_is_configured(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeGateway:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(ai_dependencies, "BedrockAiGenerationGateway", FakeGateway)
    settings = Settings(
        AI_PROVIDER_ENABLED=True,
        AI_PROVIDER_NAME="bedrock",
        AI_PROVIDER_MODEL="deepseek.v3.2",
        AI_BEDROCK_REGION="us-east-1",
        AI_BEDROCK_TIMEOUT_SECONDS=15,
        AI_BEDROCK_MAX_RETRIES=3,
    )

    gateway = ai_dependencies.get_ai_generation_gateway(settings=settings)

    assert isinstance(gateway, FakeGateway)
    assert captured == {
        "region": "us-east-1",
        "model": "deepseek.v3.2",
        "timeout_seconds": 15.0,
        "max_retries": 3,
        "provider_name": "bedrock",
    }


def test_ai_runtime_status_reports_incomplete_config() -> None:
    settings = Settings(
        AI_PROVIDER_ENABLED=True,
        AI_PROVIDER_NAME="bedrock",
        AI_PROVIDER_MODEL="deepseek.v3.2",
        AI_BEDROCK_REGION="",
    )

    status = ai_dependencies.get_ai_runtime_status(settings)

    assert status == {
        "provider": "bedrock",
        "configured": False,
        "ready": False,
        "reason": "incomplete-config",
        "missing_fields": ["AI_BEDROCK_REGION"],
    }


def test_ai_runtime_status_reports_sdk_unavailable(monkeypatch) -> None:
    class FakeGateway:
        def __init__(self, **kwargs) -> None:
            raise RuntimeError("boto3 missing")

    monkeypatch.setattr(ai_dependencies, "BedrockAiGenerationGateway", FakeGateway)
    settings = Settings(
        AI_PROVIDER_ENABLED=True,
        AI_PROVIDER_NAME="bedrock",
        AI_PROVIDER_MODEL="deepseek.v3.2",
        AI_BEDROCK_REGION="us-east-1",
        AI_BEDROCK_TIMEOUT_SECONDS=15,
        AI_BEDROCK_MAX_RETRIES=3,
    )

    status = ai_dependencies.get_ai_runtime_status(settings)

    assert status == {
        "provider": "bedrock",
        "configured": True,
        "ready": False,
        "reason": "sdk-unavailable",
        "missing_fields": [],
    }
