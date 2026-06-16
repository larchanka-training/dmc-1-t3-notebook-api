from __future__ import annotations

import httpx
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.auth.models import User
from app.features.notebooks.repository import NotebookRepository

API = settings.API_V1_STR

SNAPSHOT = {
    "title": "A",
    "tags": ["reference"],
    "blocks": [
        {
            "id": "b1",
            "type": "code",
            "content": {"language": "javascript", "source": "1 + 1"},
            "meta": {"tags": ["ex"]},
        }
    ],
    "metadata": {"version": 1},
}


def _create_payload(title: str = "A") -> dict:
    return {"title": title, "content_snapshot": {**SNAPSHOT, "title": title}}


async def _other_users_notebook(db_session: AsyncSession) -> str:
    other = User(email="stranger@example.com")
    db_session.add(other)
    await db_session.flush()
    notebook = await NotebookRepository(db_session).create(
        owner_id=other.id, title="Theirs", content_snapshot=SNAPSHOT
    )
    return str(notebook.id)


async def test_get_own_notebook_returns_full_response(
    authenticated_client: httpx.AsyncClient,
) -> None:
    created = await authenticated_client.post(
        f"{API}/notebooks", json=_create_payload("Mine")
    )
    notebook_id = created.json()["id"]

    response = await authenticated_client.get(f"{API}/notebooks/{notebook_id}")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["id"] == notebook_id
    assert body["tags"] == ["reference"]
    assert body["blocks"][0]["meta"]["tags"] == ["ex"]


async def test_get_foreign_notebook_returns_404(
    authenticated_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    foreign_id = await _other_users_notebook(db_session)
    response = await authenticated_client.get(f"{API}/notebooks/{foreign_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_unknown_notebook_returns_404(
    authenticated_client: httpx.AsyncClient,
) -> None:
    import uuid

    response = await authenticated_client.get(f"{API}/notebooks/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_patch_renames_and_preserves_tags(
    authenticated_client: httpx.AsyncClient,
) -> None:
    created = await authenticated_client.post(
        f"{API}/notebooks", json=_create_payload("Old")
    )
    notebook_id = created.json()["id"]

    response = await authenticated_client.patch(
        f"{API}/notebooks/{notebook_id}", json={"title": "Renamed"}
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["title"] == "Renamed"
    assert body["tags"] == ["reference"]
    assert body["blocks"][0]["meta"]["tags"] == ["ex"]


async def test_patch_foreign_notebook_returns_404(
    authenticated_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    foreign_id = await _other_users_notebook(db_session)
    response = await authenticated_client.patch(
        f"{API}/notebooks/{foreign_id}", json={"title": "Hacked"}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
