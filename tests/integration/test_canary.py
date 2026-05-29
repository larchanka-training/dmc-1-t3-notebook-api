"""Integration canary. Auto-tagged `integration` by tests/conftest.py."""
import httpx

from app.core.config import settings


async def test_health_endpoint(client: httpx.AsyncClient) -> None:
    """App boots, Alembic migrations applied, /api/v1/system/health returns 200."""
    response = await client.get(f"{settings.API_V1_STR}/system/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
