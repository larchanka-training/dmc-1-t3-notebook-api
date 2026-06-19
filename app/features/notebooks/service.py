from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.features.notebooks.models import Notebook
from app.features.notebooks.repository import NotebookRepository
from app.features.notebooks.schemas import (
    NotebookCreateRequest,
    NotebookResponse,
    NotebookSnapshot,
    NotebookSummary,
    NotebookSyncRequest,
)


@dataclass
class NotebookSyncConflict:
    """Returned by NotebookService.sync when base_revision is stale."""

    server_revision: int


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
    """Owner-scoped notebook use cases over the repository.

    Revision / sync-readiness invariants (Version 1, see api/docs/persistence.md):
    - a created notebook starts at ``revision = 1`` and ``last_synced_at = None``;
    - metadata updates (rename) keep ``revision`` and ``last_synced_at`` untouched
      and never emulate sync via ``base_revision``;
    - ``revision``/timestamps are exposed on every response so a later
      ``/notebooks/{id}/sync`` can build on this contract without changing the
      stored snapshot shape.
    """

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
        # Build the response before committing: commit expires ORM attributes,
        # and re-reading them would attempt lazy IO outside the async context.
        response = build_notebook_response(notebook)
        await self.repository.session.commit()
        return response

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
        response = build_notebook_response(notebook)
        await self.repository.session.commit()
        return response

    async def delete(self, *, owner_id: uuid.UUID, notebook_id: uuid.UUID) -> bool:
        notebook = await self.repository.get_owned(
            notebook_id=notebook_id, owner_id=owner_id
        )
        if notebook is None:
            return False
        await self.repository.delete(notebook)
        await self.repository.session.commit()
        return True

    async def sync(
        self,
        *,
        owner_id: uuid.UUID,
        notebook_id: uuid.UUID,
        payload: NotebookSyncRequest,
    ) -> NotebookResponse | NotebookSyncConflict | None:
        notebook = await self.repository.get_owned(
            notebook_id=notebook_id, owner_id=owner_id
        )
        if notebook is None:
            return None
        if payload.base_revision != notebook.revision:
            return NotebookSyncConflict(server_revision=notebook.revision)

        aligned = align_snapshot(
            payload.content_snapshot,
            notebook_id=notebook.id,
            title=payload.content_snapshot.title,
        )
        notebook = await self.repository.update(
            notebook,
            title=payload.content_snapshot.title,
            content_snapshot=aligned.model_dump(),
            revision=notebook.revision + 1,
            last_synced_at=datetime.now(UTC),
        )
        response = build_notebook_response(notebook)
        await self.repository.session.commit()
        return response
