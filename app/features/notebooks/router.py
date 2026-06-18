from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.features.auth.dependencies import get_current_user
from app.features.auth.schemas import UserSummary
from app.features.notebooks.dependencies import get_notebook_service
from app.features.notebooks.schemas import (
    NotebookCreateRequest,
    NotebookPatchRequest,
    NotebookResponse,
    NotebookSummary,
    NotebookSyncConflictResponse,
    NotebookSyncRequest,
)
from app.features.notebooks.service import NotebookService, NotebookSyncConflict

router = APIRouter(prefix="/notebooks", tags=["notebooks"])

NOTEBOOK_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found."
)


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


@router.get(
    "/{notebook_id}",
    response_model=NotebookResponse,
    summary="Get one of the current user's notebooks",
)
async def get_notebook(
    notebook_id: uuid.UUID,
    current_user: UserSummary = Depends(get_current_user),
    service: NotebookService = Depends(get_notebook_service),
) -> NotebookResponse:
    result = await service.get(
        owner_id=uuid.UUID(current_user.id), notebook_id=notebook_id
    )
    if result is None:
        raise NOTEBOOK_NOT_FOUND
    return result


@router.delete(
    "/{notebook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notebook",
)
async def delete_notebook(
    notebook_id: uuid.UUID,
    current_user: UserSummary = Depends(get_current_user),
    service: NotebookService = Depends(get_notebook_service),
) -> None:
    deleted = await service.delete(
        owner_id=uuid.UUID(current_user.id), notebook_id=notebook_id
    )
    if not deleted:
        raise NOTEBOOK_NOT_FOUND


@router.patch(
    "/{notebook_id}",
    response_model=NotebookResponse,
    summary="Rename a notebook (metadata update)",
)
async def patch_notebook(
    notebook_id: uuid.UUID,
    payload: NotebookPatchRequest,
    current_user: UserSummary = Depends(get_current_user),
    service: NotebookService = Depends(get_notebook_service),
) -> NotebookResponse:
    owner_id = uuid.UUID(current_user.id)
    if payload.title is not None:
        result = await service.rename(
            owner_id=owner_id, notebook_id=notebook_id, title=payload.title
        )
    else:
        result = await service.get(owner_id=owner_id, notebook_id=notebook_id)
    if result is None:
        raise NOTEBOOK_NOT_FOUND
    return result


@router.post(
    "/{notebook_id}/sync",
    response_model=NotebookResponse,
    responses={status.HTTP_409_CONFLICT: {"model": NotebookSyncConflictResponse}},
    summary="Sync (push) a notebook snapshot with an optimistic revision check",
)
async def sync_notebook(
    notebook_id: uuid.UUID,
    payload: NotebookSyncRequest,
    current_user: UserSummary = Depends(get_current_user),
    service: NotebookService = Depends(get_notebook_service),
):
    result = await service.sync(
        owner_id=uuid.UUID(current_user.id),
        notebook_id=notebook_id,
        payload=payload,
    )
    if result is None:
        raise NOTEBOOK_NOT_FOUND
    if isinstance(result, NotebookSyncConflict):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "notebook_sync_conflict",
                    "message": "The notebook was updated on the server.",
                },
                "server_revision": result.server_revision,
            },
        )
    return result
