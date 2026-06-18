from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.features.ai.dependencies import get_ai_service
from app.features.ai.schemas import (
    AiCodeGenerateRequest,
    AiCodeGenerateSuccessResponse,
    AiErrorResponse,
)
from app.features.ai.service import AiService
from app.features.auth.dependencies import get_current_user
from app.features.auth.schemas import UserSummary

router = APIRouter(prefix="/ai", tags=["ai"])

AI_ERROR_RESPONSES = {
    400: {"model": AiErrorResponse, "description": "AI prompt rejected or unsafe"},
    403: {"model": AiErrorResponse, "description": "Notebook access is forbidden"},
    422: {"model": AiErrorResponse, "description": "AI request is invalid"},
    502: {"model": AiErrorResponse, "description": "AI provider response is invalid"},
    503: {"model": AiErrorResponse, "description": "AI provider is unavailable"},
    504: {"model": AiErrorResponse, "description": "AI provider timed out"},
}


@router.post(
    "/code-blocks/generate",
    response_model=AiCodeGenerateSuccessResponse,
    responses=AI_ERROR_RESPONSES,
    summary="Generate a JavaScript code block proposal from a text block",
)
async def generate_code_block(
    payload: AiCodeGenerateRequest,
    current_user: UserSummary = Depends(get_current_user),
    service: AiService = Depends(get_ai_service),
) -> AiCodeGenerateSuccessResponse:
    return await service.generate_code(
        owner_id=uuid.UUID(current_user.id),
        payload=payload,
    )
