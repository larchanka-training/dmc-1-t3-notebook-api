from __future__ import annotations

import uuid
from typing import Any

from app.features.notebooks.models import Notebook
from app.features.notebooks.schemas import (
    NotebookResponse,
    NotebookSnapshot,
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
