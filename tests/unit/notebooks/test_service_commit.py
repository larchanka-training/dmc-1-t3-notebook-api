from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.features.notebooks.schemas import NotebookCreateRequest
from app.features.notebooks.service import NotebookService

VALID_SNAPSHOT = {"title": "T", "tags": [], "blocks": [], "metadata": {"version": 1}}


def _row(snapshot: dict) -> SimpleNamespace:
    now = datetime(2026, 6, 16, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        title="T",
        content_snapshot=snapshot,
        revision=1,
        created_at=now,
        updated_at=now,
        last_synced_at=None,
    )


class _FakeRepo:
    def __init__(self) -> None:
        self.session = SimpleNamespace(commit=AsyncMock())

    async def create(self, *, owner_id, title, content_snapshot, revision=1):
        return _row(content_snapshot)

    async def update(self, notebook, *, title=None, content_snapshot=None, **_):
        if title is not None:
            notebook.title = title
        if content_snapshot is not None:
            notebook.content_snapshot = content_snapshot
        return notebook

    async def get_owned(self, *, notebook_id, owner_id):
        return _row(dict(VALID_SNAPSHOT))

    async def delete(self, notebook):
        return None


def _create_payload() -> NotebookCreateRequest:
    return NotebookCreateRequest.model_validate(
        {"title": "T", "content_snapshot": VALID_SNAPSHOT}
    )


async def test_create_commits_the_transaction() -> None:
    repo = _FakeRepo()
    await NotebookService(repo).create(owner_id=uuid.uuid4(), payload=_create_payload())
    repo.session.commit.assert_awaited_once()


async def test_rename_commits_the_transaction() -> None:
    repo = _FakeRepo()
    await NotebookService(repo).rename(
        owner_id=uuid.uuid4(), notebook_id=uuid.uuid4(), title="New"
    )
    repo.session.commit.assert_awaited_once()


async def test_delete_commits_the_transaction() -> None:
    repo = _FakeRepo()
    await NotebookService(repo).delete(owner_id=uuid.uuid4(), notebook_id=uuid.uuid4())
    repo.session.commit.assert_awaited_once()
