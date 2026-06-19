from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import User
from app.features.notebooks.repository import NotebookRepository

SNAPSHOT = {
    "id": "nb-1",
    "title": "T",
    "tags": ["reference"],
    "blocks": [
        {
            "id": "b1",
            "type": "text",
            "content": {"markdown": "# Hi"},
            "meta": {"tags": ["intro"]},
        }
    ],
    "metadata": {"version": 1},
}


async def _make_user(db_session: AsyncSession, email: str = "owner@example.com") -> User:
    user = User(email=email)
    db_session.add(user)
    await db_session.flush()
    return user


async def test_create_sets_defaults_and_get_round_trips_tags(
    db_session: AsyncSession,
) -> None:
    owner = await _make_user(db_session)
    repo = NotebookRepository(db_session)

    notebook = await repo.create(
        owner_id=owner.id, title="T", content_snapshot=SNAPSHOT
    )
    assert notebook.id is not None
    assert notebook.revision == 1

    got = await repo.get_by_id(notebook.id)
    assert got is not None
    assert got.content_snapshot["tags"] == ["reference"]
    assert got.content_snapshot["blocks"][0]["meta"]["tags"] == ["intro"]


async def test_list_for_owner_returns_only_owned(db_session: AsyncSession) -> None:
    owner = await _make_user(db_session, "o1@example.com")
    other = await _make_user(db_session, "o2@example.com")
    repo = NotebookRepository(db_session)

    await repo.create(owner_id=owner.id, title="A", content_snapshot=SNAPSHOT)
    await repo.create(owner_id=owner.id, title="B", content_snapshot=SNAPSHOT)
    await repo.create(owner_id=other.id, title="C", content_snapshot=SNAPSHOT)

    owned = await repo.list_for_owner(owner.id)
    assert {nb.title for nb in owned} == {"A", "B"}


async def test_update_changes_fields_and_keeps_tags(db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    repo = NotebookRepository(db_session)
    notebook = await repo.create(
        owner_id=owner.id, title="T", content_snapshot=SNAPSHOT
    )

    updated = await repo.update(notebook, title="Renamed", revision=2)
    assert updated.title == "Renamed"
    assert updated.revision == 2
    assert updated.content_snapshot["blocks"][0]["meta"]["tags"] == ["intro"]


async def test_delete_removes_notebook(db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    repo = NotebookRepository(db_session)
    notebook = await repo.create(
        owner_id=owner.id, title="T", content_snapshot=SNAPSHOT
    )

    await repo.delete(notebook)
    assert await repo.get_by_id(notebook.id) is None
