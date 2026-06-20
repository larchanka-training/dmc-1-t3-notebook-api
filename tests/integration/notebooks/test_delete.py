from __future__ import annotations

import uuid

import httpx
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.auth.models import User
from app.features.notebooks.repository import NotebookRepository

API = settings.API_V1_STR

SNAPSHOT = {
    "title": "A",
    "tags": [],
    "blocks": [],
    "metadata": {"version": 1},
}


def _create_payload(title: str = "A") -> dict:
    return {"title": title, "content_snapshot": {**SNAPSHOT, "title": title}}


async def test_delete_own_notebook_then_get_is_404(
    authenticated_client: httpx.AsyncClient,
) -> None:
    created = await authenticated_client.post(
        f"{API}/notebooks", json=_create_payload("Doomed")
    )
    notebook_id = created.json()["id"]

    deleted = await authenticated_client.delete(f"{API}/notebooks/{notebook_id}")
    assert deleted.status_code == status.HTTP_204_NO_CONTENT

    after = await authenticated_client.get(f"{API}/notebooks/{notebook_id}")
    assert after.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_unknown_notebook_returns_404(
    authenticated_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_client.delete(f"{API}/notebooks/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_foreign_notebook_returns_404(
    authenticated_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    other = User(email="stranger@example.com")
    db_session.add(other)
    await db_session.flush()
    notebook = await NotebookRepository(db_session).create(
        owner_id=other.id, title="Theirs", content_snapshot=SNAPSHOT
    )

    response = await authenticated_client.delete(f"{API}/notebooks/{notebook.id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_anonymous_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.delete(f"{API}/notebooks/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
