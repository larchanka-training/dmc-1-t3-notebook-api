from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Application error with stable code for API clients."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


def error_payload(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    headers: dict[str, str] = {}
    if exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)

    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message),
        headers=headers,
    )
