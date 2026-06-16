from __future__ import annotations

import uuid
from typing import Any

from app.features.notebooks.models import Notebook
from app.features.notebooks.repository import NotebookRepository
from app.features.notebooks.schemas import (
    NotebookCreateRequest,
    NotebookResponse,
    NotebookSnapshot,
    NotebookSummary,
)


def validate_snapshot(raw: dict[str, Any]) -> NotebookSnapshot:
    """Validate a raw content snapshot against the Version 1 notebook rules."""
    return NotebookSnapshot.model_validate(raw)


def align_snapshot(
    snapshot: NotebookSnapshot,
    *,
    notebook_id: uuid.UUID,
    title: str,
) -> NotebookSnapshot:
    """Force the snapshot's `id`/`title` to match the persisted row metadata."""
    return snapshot.model_copy(update={"id": str(notebook_id), "title": title})


def build_notebook_response(notebook: Notebook) -> NotebookResponse:
    """Combine durable row metadata with the validated snapshot body."""
    snapshot = validate_snapshot(notebook.content_snapshot)
    return NotebookResponse(
        id=notebook.id,
        title=notebook.title,
        tags=snapshot.tags,
        blocks=snapshot.blocks,
        revision=notebook.revision,
        created_at=notebook.created_at,
        updated_at=notebook.updated_at,
        last_synced_at=notebook.last_synced_at,
    )


def build_notebook_summary(notebook: Notebook) -> NotebookSummary:
    """Build a list-item summary, sourcing tags from the stored snapshot."""
    snapshot = validate_snapshot(notebook.content_snapshot)
    return NotebookSummary(
        id=notebook.id,
        title=notebook.title,
        tags=snapshot.tags,
        revision=notebook.revision,
        created_at=notebook.created_at,
        updated_at=notebook.updated_at,
    )


class NotebookService:
    """Owner-scoped notebook use cases over the repository."""

    def __init__(self, repository: NotebookRepository) -> None:
        self.repository = repository

    async def create(
        self, *, owner_id: uuid.UUID, payload: NotebookCreateRequest
    ) -> NotebookResponse:
        notebook = await self.repository.create(
            owner_id=owner_id,
            title=payload.title,
            content_snapshot=payload.content_snapshot.model_dump(),
            revision=1,
        )
        aligned = align_snapshot(
            payload.content_snapshot, notebook_id=notebook.id, title=payload.title
        )
        notebook = await self.repository.update(
            notebook, content_snapshot=aligned.model_dump()
        )
        return build_notebook_response(notebook)

    async def list_summaries(self, owner_id: uuid.UUID) -> list[NotebookSummary]:
        notebooks = await self.repository.list_for_owner(owner_id)
        return [build_notebook_summary(notebook) for notebook in notebooks]

    async def get(
        self, *, owner_id: uuid.UUID, notebook_id: uuid.UUID
    ) -> NotebookResponse | None:
        notebook = await self.repository.get_owned(
            notebook_id=notebook_id, owner_id=owner_id
        )
        return build_notebook_response(notebook) if notebook is not None else None

    async def rename(
        self, *, owner_id: uuid.UUID, notebook_id: uuid.UUID, title: str
    ) -> NotebookResponse | None:
        notebook = await self.repository.get_owned(
            notebook_id=notebook_id, owner_id=owner_id
        )
        if notebook is None:
            return None
        aligned = align_snapshot(
            validate_snapshot(notebook.content_snapshot),
            notebook_id=notebook.id,
            title=title,
        )
        notebook = await self.repository.update(
            notebook, title=title, content_snapshot=aligned.model_dump()
        )
        return build_notebook_response(notebook)
