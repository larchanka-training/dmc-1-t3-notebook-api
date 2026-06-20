from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.features.ai.schemas import AiErrorResponse

AI_GENERATE_ROUTE_PATH = f"{settings.API_V1_STR}/ai/code-blocks/generate"


class AiRouteError(Exception):
    def __init__(self, status_code: int, payload: AiErrorResponse) -> None:
        super().__init__(payload.message)
        self.status_code = status_code
        self.payload = payload


def build_ai_error(
    *,
    status_code: int,
    error_code: str,
    message: str,
    retryable: bool,
    request_id: str | None = None,
) -> AiRouteError:
    return AiRouteError(
        status_code=status_code,
        payload=AiErrorResponse(
            request_id=request_id,
            status="error",
            error_code=error_code,
            message=message,
            retryable=retryable,
        ),
    )


def ai_json_response(payload: AiErrorResponse, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(by_alias=True, exclude_none=True),
    )


def build_ai_invalid_request_response(request_id: str | None = None) -> JSONResponse:
    return ai_json_response(
        AiErrorResponse(
            request_id=request_id,
            status="error",
            error_code="AI_INVALID_REQUEST",
            message="The AI request is invalid.",
            retryable=False,
        ),
        status_code=422,
    )


def is_ai_generate_request(request: Request) -> bool:
    return (
        request.method.upper() == "POST"
        and request.url.path == AI_GENERATE_ROUTE_PATH
    )
