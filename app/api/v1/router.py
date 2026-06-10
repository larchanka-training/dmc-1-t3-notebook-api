from fastapi import APIRouter

from app.api.v1.routes import health as legacy_health
from app.features.system.router import router as system_router

api_v1_router = APIRouter()

# Feature routers (architecture: features/<name>/router.py)
api_v1_router.include_router(system_router)

# Legacy /health alias at v1 root for backward compatibility
api_v1_router.include_router(legacy_health.router)

# Placeholders for future feature routers:
# from app.features.auth.router import router as auth_router
# from app.features.notebooks.router import router as notebooks_router
# from app.features.ai.router import router as ai_router
# api_v1_router.include_router(auth_router)
# api_v1_router.include_router(notebooks_router)
# api_v1_router.include_router(ai_router)
