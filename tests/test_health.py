from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings


def test_health_check_endpoint_returns_valid_payload(client: TestClient) -> None:
    """
    Asserts compliance against infrastructure payload metadata and contract expectations.
    """
    target_url = f"{settings.API_V1_STR}/health"
    response = client.get(target_url)

    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["version"] == settings.VERSION
    assert payload["environment"] == settings.ENVIRONMENT


def test_system_health_endpoint_returns_valid_payload(client: TestClient) -> None:
    """
    Canonical system health route per api_architecture.md: GET /api/v1/system/health.
    """
    target_url = f"{settings.API_V1_STR}/system/health"
    response = client.get(target_url)

    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["version"] == settings.VERSION
    assert payload["environment"] == settings.ENVIRONMENT


def test_health_check_includes_cors_headers_for_allowed_origin(client: TestClient) -> None:
    allowed_origin = settings.BACKEND_CORS_ORIGINS[0]
    response = client.get(
        f"{settings.API_V1_STR}/health",
        headers={"Origin": allowed_origin},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["access-control-allow-origin"] == allowed_origin
