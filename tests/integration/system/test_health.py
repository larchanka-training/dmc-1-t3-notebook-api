"""
Integration tests for the health check endpoints.

Ports the three behavioural tests that were removed from tests/test_health.py
into the async integration suite, covering:
  - GET /api/v1/health (legacy alias)
  - GET /api/v1/system/health (canonical)
  - CORS headers on the health route
"""
from __future__ import annotations

import httpx
from fastapi import status

from app.core.config import settings


async def test_health_check_endpoint_returns_valid_payload(
    client: httpx.AsyncClient,
) -> None:
    """Legacy /api/v1/health alias returns status, version, and environment."""
    response = await client.get(f"{settings.API_V1_STR}/health")

    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["version"] == settings.VERSION
    assert payload["environment"] == settings.ENVIRONMENT
    assert payload["ai"]["provider"] == settings.AI_PROVIDER_NAME
    assert payload["ai"]["ready"] is False


async def test_system_health_endpoint_returns_valid_payload(
    client: httpx.AsyncClient,
) -> None:
    """Canonical GET /api/v1/system/health returns status, version, and environment."""
    response = await client.get(f"{settings.API_V1_STR}/system/health")

    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["version"] == settings.VERSION
    assert payload["environment"] == settings.ENVIRONMENT
    assert set(payload["ai"]) == {
        "provider",
        "configured",
        "ready",
        "reason",
        "missing_fields",
    }


async def test_health_check_includes_cors_headers_for_allowed_origin(
    client: httpx.AsyncClient,
) -> None:
    """CORS middleware returns the correct allow-origin header for a permitted origin."""
    response = await client.get(
        f"{settings.API_V1_STR}/health",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
