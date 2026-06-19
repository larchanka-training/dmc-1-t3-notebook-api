import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.router import api_v1_router
from app.features.ai.errors import (
    AiRouteError,
    ai_json_response,
    build_ai_invalid_request_response,
    is_ai_generate_request,
)
from app.features.auth.errors import AuthError

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages explicit enterprise application lifecycle boundaries.
    """
    setup_logging(log_level=settings.LOG_LEVEL)
    logger.info("Application logging initialized.")
    logger.info(
        "Starting application. Environment: %s, Version: %s",
        settings.ENVIRONMENT,
        settings.VERSION,
    )

    yield

    logger.info("Application teardown completed.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthError)
async def auth_error_exception_handler(
    request: Request, exc: AuthError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(AiRouteError)
async def ai_route_error_exception_handler(
    request: Request, exc: AiRouteError
) -> JSONResponse:
    return ai_json_response(exc.payload, exc.status_code)


@app.exception_handler(RequestValidationError)
async def request_validation_error_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if is_ai_generate_request(request):
        return build_ai_invalid_request_response()
    return await request_validation_exception_handler(request, exc)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    """Log every request with method, path, status and duration."""
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled error: %s %s", request.method, request.url.path
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# Bind global configuration object into app state
app.state.settings = settings

# Mount consolidated v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
