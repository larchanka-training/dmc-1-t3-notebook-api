import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import AppError, app_error_handler
from app.core.logging import setup_logging
from app.api.v1.router import api_v1_router

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

app.add_exception_handler(AppError, app_error_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
