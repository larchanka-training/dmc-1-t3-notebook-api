from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.features.ai.repository import AiRepository
from app.features.ai.service import AiService
from app.features.notebooks.repository import NotebookRepository
from app.integrations.ai import (
    AiGenerationGateway,
    BedrockAiGenerationGateway,
    UnavailableAiGenerationGateway,
)


def get_ai_runtime_status(settings: Settings) -> dict[str, object]:
    if not settings.AI_PROVIDER_ENABLED:
        return {
            "provider": settings.AI_PROVIDER_NAME,
            "configured": False,
            "ready": False,
            "reason": "disabled",
            "missing_fields": ["AI_PROVIDER_ENABLED"],
        }

    missing_fields = settings.ai_bedrock_runtime_missing_fields
    if missing_fields:
        return {
            "provider": settings.AI_PROVIDER_NAME,
            "configured": False,
            "ready": False,
            "reason": "incomplete-config",
            "missing_fields": missing_fields,
        }

    try:
        BedrockAiGenerationGateway(
            region=settings.AI_BEDROCK_REGION,
            model=settings.AI_PROVIDER_MODEL,
            timeout_seconds=settings.AI_BEDROCK_TIMEOUT_SECONDS,
            max_retries=settings.AI_BEDROCK_MAX_RETRIES,
            provider_name=settings.AI_PROVIDER_NAME,
        )
    except RuntimeError:
        return {
            "provider": settings.AI_PROVIDER_NAME,
            "configured": True,
            "ready": False,
            "reason": "sdk-unavailable",
            "missing_fields": [],
        }

    return {
        "provider": settings.AI_PROVIDER_NAME,
        "configured": True,
        "ready": True,
        "reason": "ready",
        "missing_fields": [],
    }


def get_ai_repository(db: AsyncSession = Depends(get_db)) -> AiRepository:
    return AiRepository(NotebookRepository(db))


def get_ai_generation_gateway(
    settings: Settings = Depends(get_settings),
) -> AiGenerationGateway:
    runtime_status = get_ai_runtime_status(settings)
    if runtime_status["ready"]:
        try:
            return BedrockAiGenerationGateway(
                region=settings.AI_BEDROCK_REGION,
                model=settings.AI_PROVIDER_MODEL,
                timeout_seconds=settings.AI_BEDROCK_TIMEOUT_SECONDS,
                max_retries=settings.AI_BEDROCK_MAX_RETRIES,
                provider_name=settings.AI_PROVIDER_NAME,
            )
        except RuntimeError:
            pass

    return UnavailableAiGenerationGateway(
        provider_name=settings.AI_PROVIDER_NAME,
        model=settings.AI_PROVIDER_MODEL,
    )


def get_ai_service(
    repository: AiRepository = Depends(get_ai_repository),
    gateway: AiGenerationGateway = Depends(get_ai_generation_gateway),
) -> AiService:
    return AiService(repository=repository, gateway=gateway)
