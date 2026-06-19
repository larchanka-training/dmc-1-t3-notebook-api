from __future__ import annotations

import httpx
from fastapi import status

from app.core.config import settings

API = settings.API_V1_STR

SNAPSHOT = {"title": "A", "tags": [], "blocks": [], "metadata": {"version": 1}}


def _create_payload(title: str = "A") -> dict:
    return {"title": title, "content_snapshot": {**SNAPSHOT, "title": title}}


async def test_created_notebook_starts_at_revision_1_and_unsynced(
    authenticated_client: httpx.AsyncClient,
) -> None:
    created = await authenticated_client.post(
        f"{API}/notebooks", json=_create_payload()
    )
    assert created.status_code == status.HTTP_201_CREATED
    body = created.json()
    assert body["revision"] == 1
    assert body["last_synced_at"] is None
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


async def test_rename_does_not_bump_revision_or_set_last_synced_at(
    authenticated_client: httpx.AsyncClient,
) -> None:
    created = await authenticated_client.post(
        f"{API}/notebooks", json=_create_payload("Old")
    )
    notebook_id = created.json()["id"]

    renamed = await authenticated_client.patch(
        f"{API}/notebooks/{notebook_id}", json={"title": "New"}
    )
    body = renamed.json()
    # Metadata rename must not emulate a sync write.
    assert body["revision"] == 1
    assert body["last_synced_at"] is None


async def test_list_summary_exposes_revision_for_sync_readiness(
    authenticated_client: httpx.AsyncClient,
) -> None:
    await authenticated_client.post(f"{API}/notebooks", json=_create_payload())
    response = await authenticated_client.get(f"{API}/notebooks")
    summary = response.json()[0]
    assert summary["revision"] == 1
    assert "created_at" in summary
    assert "updated_at" in summary
