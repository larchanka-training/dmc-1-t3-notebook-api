from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.features.auth.dependencies import get_current_user
from app.features.auth.schemas import UserSummary
from app.features.notebooks.dependencies import get_notebook_service
from app.features.notebooks.schemas import (
    NotebookCreateRequest,
    NotebookResponse,
    NotebookSummary,
)
from app.features.notebooks.service import NotebookService

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.post(
    "",
    response_model=NotebookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a notebook",
)
async def create_notebook(
    payload: NotebookCreateRequest,
    current_user: UserSummary = Depends(get_current_user),
    service: NotebookService = Depends(get_notebook_service),
) -> NotebookResponse:
    return await service.create(
        owner_id=uuid.UUID(current_user.id), payload=payload
    )


@router.get(
    "",
    response_model=list[NotebookSummary],
    summary="List the current user's notebooks",
)
async def list_notebooks(
    current_user: UserSummary = Depends(get_current_user),
    service: NotebookService = Depends(get_notebook_service),
) -> list[NotebookSummary]:
    return await service.list_summaries(uuid.UUID(current_user.id))
