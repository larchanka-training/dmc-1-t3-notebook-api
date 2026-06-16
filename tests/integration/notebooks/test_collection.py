from __future__ import annotations

import httpx
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

API = settings.API_V1_STR

SNAPSHOT = {
    "title": "A",
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


def _create_payload(title: str = "A") -> dict:
    return {"title": title, "content_snapshot": {**SNAPSHOT, "title": title}}


async def test_anonymous_list_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API}/notebooks")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_create_returns_201_with_revision_and_tags(
    authenticated_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_client.post(
        f"{API}/notebooks", json=_create_payload("My notebook")
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["revision"] == 1
    assert body["title"] == "My notebook"
    assert body["tags"] == ["reference"]
    assert body["blocks"][0]["meta"]["tags"] == ["intro"]


async def test_list_returns_only_current_user_summaries(
    authenticated_client: httpx.AsyncClient,
    authenticated_user: dict,
    db_session: AsyncSession,
) -> None:
    # One notebook for the authenticated user via the API.
    await authenticated_client.post(f"{API}/notebooks", json=_create_payload("Mine"))

    # Another user's notebook inserted directly must not leak into the list.
    from app.features.auth.models import User
    from app.features.notebooks.repository import NotebookRepository

    other = User(email="other@example.com")
    db_session.add(other)
    await db_session.flush()
    await NotebookRepository(db_session).create(
        owner_id=other.id, title="Theirs", content_snapshot=SNAPSHOT
    )

    response = await authenticated_client.get(f"{API}/notebooks")
    assert response.status_code == status.HTTP_200_OK
    titles = [item["title"] for item in response.json()]
    assert titles == ["Mine"]
    assert all("tags" in item for item in response.json())
