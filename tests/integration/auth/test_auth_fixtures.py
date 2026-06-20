from __future__ import annotations

import httpx
from fastapi import status

from app.core.config import settings


async def test_authenticated_client_fixture_bootstraps_real_session(
    authenticated_client: httpx.AsyncClient,
    authenticated_user: dict[str, object],
) -> None:
    response = await authenticated_client.get(f"{settings.API_V1_STR}/auth/session")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "authenticated": True,
        "user": authenticated_user,
    }
