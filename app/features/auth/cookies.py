from __future__ import annotations

from fastapi import Request, Response

from app.core.config import Settings


def set_auth_session_cookie(
    response: Response,
    session_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.AUTH_SESSION_COOKIE_NAME,
        value=session_token,
        max_age=settings.AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.AUTH_SESSION_COOKIE_SECURE,
        samesite=settings.AUTH_SESSION_COOKIE_SAMESITE,
        path=settings.AUTH_SESSION_COOKIE_PATH,
        domain=settings.AUTH_SESSION_COOKIE_DOMAIN,
    )


def clear_auth_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.AUTH_SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.AUTH_SESSION_COOKIE_SECURE,
        samesite=settings.AUTH_SESSION_COOKIE_SAMESITE,
        path=settings.AUTH_SESSION_COOKIE_PATH,
        domain=settings.AUTH_SESSION_COOKIE_DOMAIN,
    )


def read_auth_session_cookie(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.AUTH_SESSION_COOKIE_NAME)

