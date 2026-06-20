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
    "tags": ["t"],
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


def _create_payload(title: str = "A") -> dict:
    return {"title": title, "content_snapshot": {**SNAPSHOT, "title": title}}


def _edited_snapshot(title: str, source_markdown: str) -> dict:
    return {
        **SNAPSHOT,
        "title": title,
        "blocks": [
            {
                "id": "b1",
                "type": "text",
                "content": {"markdown": source_markdown},
                "meta": {"tags": ["intro"]},
            }
        ],
    }


async def _create(client: httpx.AsyncClient) -> dict:
    response = await client.post(f"{API}/notebooks", json=_create_payload("Mine"))
    return response.json()


async def test_sync_pushes_snapshot_and_increments_revision(
    authenticated_client: httpx.AsyncClient,
) -> None:
    created = await _create(authenticated_client)
    notebook_id = created["id"]
    assert created["revision"] == 1

    response = await authenticated_client.post(
        f"{API}/notebooks/{notebook_id}/sync",
        json={
            "base_revision": 1,
            "content_snapshot": _edited_snapshot("Mine", "# Edited"),
        },
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["revision"] == 2
    assert body["blocks"][0]["content"]["markdown"] == "# Edited"
    assert body["last_synced_at"] is not None


async def test_sync_conflict_on_stale_base_revision_writes_nothing(
    authenticated_client: httpx.AsyncClient,
) -> None:
    created = await _create(authenticated_client)
    notebook_id = created["id"]

    response = await authenticated_client.post(
        f"{API}/notebooks/{notebook_id}/sync",
        json={
            "base_revision": 0,
            "content_snapshot": _edited_snapshot("Mine", "# Should not persist"),
        },
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    body = response.json()
    assert body["error"]["code"] == "notebook_sync_conflict"
    assert body["server_revision"] == 1

    # No write happened.
    after = await authenticated_client.get(f"{API}/notebooks/{notebook_id}")
    assert after.json()["revision"] == 1
    assert after.json()["blocks"][0]["content"]["markdown"] == "# Hi"


async def test_sync_anonymous_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.post(
        f"{API}/notebooks/{uuid.uuid4()}/sync",
        json={"base_revision": 1, "content_snapshot": SNAPSHOT},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_sync_foreign_notebook_returns_404(
    authenticated_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    other = User(email="stranger@example.com")
    db_session.add(other)
    await db_session.flush()
    notebook = await NotebookRepository(db_session).create(
        owner_id=other.id, title="Theirs", content_snapshot=SNAPSHOT
    )

    response = await authenticated_client.post(
        f"{API}/notebooks/{notebook.id}/sync",
        json={"base_revision": 1, "content_snapshot": SNAPSHOT},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_sync_rejects_invalid_snapshot_422(
    authenticated_client: httpx.AsyncClient,
) -> None:
    created = await _create(authenticated_client)
    bad = {
        "base_revision": 1,
        "content_snapshot": {
            "title": "x",
            "tags": [],
            "blocks": [
                {
                    "id": "b",
                    "type": "code",
                    "content": {"language": "python", "source": "x=1"},
                    "meta": {"tags": []},
                }
            ],
            "metadata": {"version": 1},
        },
    }
    response = await authenticated_client.post(
        f"{API}/notebooks/{created['id']}/sync", json=bad
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
