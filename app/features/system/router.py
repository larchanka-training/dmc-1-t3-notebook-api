from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings

router = APIRouter(prefix="/system", tags=["system"])


class HealthCheckResponse(BaseModel):
    status: str = Field(default="healthy", description="Current operational state")
    version: str = Field(..., description="Application semantic version")
    environment: str = Field(..., description="Active runtime environment tier")


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Perform infrastructure health assessment",
)
async def perform_health_check(
    current_settings: Settings = Depends(get_settings),
) -> HealthCheckResponse:
    """
    Liveness and Readiness probe endpoint verifying configuration
    injection and context execution lifecycle.
    """
    return HealthCheckResponse(
        status="healthy",
        version=current_settings.VERSION,
        environment=current_settings.ENVIRONMENT,
    )
