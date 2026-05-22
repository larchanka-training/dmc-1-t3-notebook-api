from fastapi import APIRouter

from app.api.v1.routes import health as legacy_health
from app.features.auth.router import router as auth_router
from app.features.system.router import router as system_router

api_v1_router = APIRouter()

api_v1_router.include_router(system_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(legacy_health.router)
