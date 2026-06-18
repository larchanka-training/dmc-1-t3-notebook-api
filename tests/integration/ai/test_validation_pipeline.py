from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.features.ai.dependencies import get_ai_generation_gateway
from app.integrations.ai import (
    AiGenerationGateway,
    AiProviderGenerateRequest,
    AiProviderGenerateResponse,
    AiProviderInvalidResponseError,
)

from .test_endpoint import _create_notebook, _payload

API = settings.API_V1_STR


class SequencedGateway(AiGenerationGateway):
    def __init__(self, outcomes: list[AiProviderGenerateResponse | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[AiProviderGenerateRequest] = []

    async def generate(
        self, request: AiProviderGenerateRequest
    ) -> AiProviderGenerateResponse:
        self.calls.append(request)
        assert self.outcomes
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def gateway_override():
    from app.main import app

    def _install(gateway: SequencedGateway) -> SequencedGateway:
        app.dependency_overrides[get_ai_generation_gateway] = lambda: gateway
        return gateway

    try:
        yield _install
    finally:
        app.dependency_overrides.pop(get_ai_generation_gateway, None)


async def test_validation_pipeline_repairs_syntax_and_returns_success(
    authenticated_client: httpx.AsyncClient,
    gateway_override,
) -> None:
    gateway = gateway_override(
        SequencedGateway(
            [
                AiProviderGenerateResponse(
                    content="function broken( {",
                    provider_name="bedrock",
                    model="anthropic.claude-3-haiku",
                ),
                AiProviderGenerateResponse(
                    content="function fixed() {\n  return 1;\n}",
                    provider_name="bedrock",
                    model="anthropic.claude-3-haiku",
                ),
            ]
        )
    )
    notebook_id = await _create_notebook(authenticated_client)

    response = await authenticated_client.post(
        f"{API}/ai/code-blocks/generate",
        json=_payload(
            notebook_id,
            prompt="Write JavaScript code that returns a number.",
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["validation"] == {
        "extractionApplied": False,
        "syntaxOk": True,
        "repairAttempts": 1,
    }
    assert body["code"] == "function fixed() {\n  return 1;\n}"
    assert len(gateway.calls) == 2
    assert gateway.calls[1].attempt == 1
    assert gateway.calls[1].repair_feedback
    assert "syntax errors" in gateway.calls[1].repair_feedback


async def test_validation_pipeline_returns_extraction_failed_after_repair_exhausted(
    authenticated_client: httpx.AsyncClient,
    gateway_override,
) -> None:
    gateway = gateway_override(
        SequencedGateway(
            [
                AiProviderGenerateResponse(
                    content="Here is an explanation without code.",
                    provider_name="bedrock",
                    model="anthropic.claude-3-haiku",
                ),
                AiProviderGenerateResponse(
                    content="Still only prose after retry.",
                    provider_name="bedrock",
                    model="anthropic.claude-3-haiku",
                ),
            ]
        )
    )
    notebook_id = await _create_notebook(authenticated_client)

    response = await authenticated_client.post(
        f"{API}/ai/code-blocks/generate",
        json=_payload(
            notebook_id,
            prompt="Write JavaScript code that parses text.",
        ),
    )

    assert response.status_code == 502
    body = response.json()
    assert body["errorCode"] == "AI_CODE_EXTRACTION_FAILED"
    assert body["retryable"] is True
    assert len(gateway.calls) == 2
    assert gateway.calls[1].attempt == 1
    assert "extractable JavaScript code" in gateway.calls[1].repair_feedback


async def test_validation_pipeline_returns_syntax_invalid_after_repair_exhausted(
    authenticated_client: httpx.AsyncClient,
    gateway_override,
) -> None:
    gateway = gateway_override(
        SequencedGateway(
            [
                AiProviderGenerateResponse(
                    content="function first( {",
                    provider_name="bedrock",
                    model="anthropic.claude-3-haiku",
                ),
                AiProviderGenerateResponse(
                    content="function second( {",
                    provider_name="bedrock",
                    model="anthropic.claude-3-haiku",
                ),
            ]
        )
    )
    notebook_id = await _create_notebook(authenticated_client)

    response = await authenticated_client.post(
        f"{API}/ai/code-blocks/generate",
        json=_payload(
            notebook_id,
            prompt="Write JavaScript code that validates input.",
        ),
    )

    assert response.status_code == 502
    body = response.json()
    assert body["errorCode"] == "AI_CODE_SYNTAX_INVALID"
    assert body["retryable"] is True
    assert len(gateway.calls) == 2


async def test_validation_pipeline_returns_comment_only_warning(
    authenticated_client: httpx.AsyncClient,
    gateway_override,
) -> None:
    gateway = gateway_override(
        SequencedGateway(
            [
                AiProviderGenerateResponse(
                    content="// This is a placeholder\n/* implement later */",
                    provider_name="bedrock",
                    model="anthropic.claude-3-haiku",
                )
            ]
        )
    )
    notebook_id = await _create_notebook(authenticated_client)

    response = await authenticated_client.post(
        f"{API}/ai/code-blocks/generate",
        json=_payload(
            notebook_id,
            prompt="Write JavaScript code scaffold for later completion.",
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["warnings"] == [
        {
            "code": "AI_COMMENT_ONLY_CODE",
            "message": "The generated code contains only comments or placeholder content.",
        }
    ]


async def test_validation_pipeline_returns_invalid_response_for_malformed_provider_payload(
    authenticated_client: httpx.AsyncClient,
    gateway_override,
) -> None:
    gateway = gateway_override(
        SequencedGateway([AiProviderInvalidResponseError("malformed upstream")])
    )
    notebook_id = await _create_notebook(authenticated_client)

    response = await authenticated_client.post(
        f"{API}/ai/code-blocks/generate",
        json=_payload(
            notebook_id,
            prompt="Write JavaScript code from this task.",
        ),
    )

    assert response.status_code == 502
    body = response.json()
    assert body["errorCode"] == "AI_RESPONSE_INVALID"
