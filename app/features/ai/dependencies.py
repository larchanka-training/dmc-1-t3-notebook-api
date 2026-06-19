from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.features.ai.repository import AiRepository
from app.features.ai.service import AiService
from app.features.notebooks.repository import NotebookRepository
from app.integrations.ai import AiGenerationGateway, UnavailableAiGenerationGateway


def get_ai_repository(db: AsyncSession = Depends(get_db)) -> AiRepository:
    return AiRepository(NotebookRepository(db))


def get_ai_generation_gateway(
    settings: Settings = Depends(get_settings),
) -> AiGenerationGateway:
    return UnavailableAiGenerationGateway(
        provider_name=settings.AI_PROVIDER_NAME,
        model=settings.AI_PROVIDER_MODEL,
    )


def get_ai_service(
    repository: AiRepository = Depends(get_ai_repository),
    gateway: AiGenerationGateway = Depends(get_ai_generation_gateway),
) -> AiService:
    return AiService(repository=repository, gateway=gateway)
