from __future__ import annotations

import httpx
import pytest
from fastapi import status

from app.core.config import settings

API = settings.API_V1_STR


def _payload(blocks: list[dict], *, tags=None, title: str = "T") -> dict:
    snapshot: dict = {
        "title": title,
        "blocks": blocks,
        "metadata": {"version": 1},
    }
    if tags is not None:
        snapshot["tags"] = tags
    return {"title": title, "content_snapshot": snapshot}


async def test_create_requires_content_snapshot(
    authenticated_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_client.post(f"{API}/notebooks", json={"title": "T"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "block",
    [
        {"id": "b", "type": "image", "content": {}, "meta": {"tags": []}},
        {
            "id": "b",
            "type": "code",
            "content": {"language": "python", "source": "x=1"},
            "meta": {"tags": []},
        },
        {
            "id": "b",
            "type": "text",
            "content": {"markdown": "x"},
            "meta": {"tags": []},
            "output": {"kind": "text", "value": "leak"},
        },
    ],
    ids=["unknown-type", "non-js-code", "runtime-output"],
)
async def test_create_rejects_invalid_blocks(
    authenticated_client: httpx.AsyncClient, block: dict
) -> None:
    response = await authenticated_client.post(
        f"{API}/notebooks", json=_payload([block])
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_create_rejects_malformed_notebook_tags(
    authenticated_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_client.post(
        f"{API}/notebooks", json=_payload([], tags="not-a-list")
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_create_defaults_missing_tags_to_empty_lists(
    authenticated_client: httpx.AsyncClient,
) -> None:
    block = {"id": "b1", "type": "text", "content": {"markdown": "# Hi"}}
    response = await authenticated_client.post(
        f"{API}/notebooks", json=_payload([block])  # no notebook tags, no block meta
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["tags"] == []
    assert body["blocks"][0]["meta"]["tags"] == []
