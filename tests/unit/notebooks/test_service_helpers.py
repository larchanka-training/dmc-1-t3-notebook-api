from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.features.notebooks.schemas import NotebookSnapshot
from app.features.notebooks.service import (
    align_snapshot,
    build_notebook_response,
)


def _snapshot() -> NotebookSnapshot:
    return NotebookSnapshot.model_validate(
        {
            "id": "stale-id",
            "title": "Stale title",
            "tags": ["t"],
            "blocks": [
                {
                    "id": "b1",
                    "type": "text",
                    "content": {"markdown": "x"},
                    "meta": {"tags": ["intro"]},
                }
            ],
            "metadata": {"version": 1},
        }
    )


def test_align_snapshot_forces_row_id_and_title() -> None:
    notebook_id = uuid.uuid4()
    aligned = align_snapshot(_snapshot(), notebook_id=notebook_id, title="Real title")
    assert aligned.id == str(notebook_id)
    assert aligned.title == "Real title"
    # tags/blocks preserved
    assert aligned.tags == ["t"]
    assert aligned.blocks[0].meta.tags == ["intro"]


class _Row:
    def __init__(self, snapshot: dict) -> None:
        self.id = uuid.uuid4()
        self.title = "Real title"
        self.revision = 3
        self.created_at = datetime(2026, 6, 16, tzinfo=UTC)
        self.updated_at = datetime(2026, 6, 16, tzinfo=UTC)
        self.last_synced_at = None
        self.content_snapshot = snapshot


def test_build_notebook_response_merges_row_meta_and_snapshot_body() -> None:
    snapshot = _snapshot()
    row = _Row(snapshot.model_dump())
    response = build_notebook_response(row)

    assert response.id == row.id
    assert response.title == "Real title"
    assert response.revision == 3
    assert response.tags == ["t"]
    assert response.blocks[0].meta.tags == ["intro"]
    assert response.last_synced_at is None
