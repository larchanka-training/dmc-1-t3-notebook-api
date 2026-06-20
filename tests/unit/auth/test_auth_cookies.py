from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.features.auth.cookies import (
    clear_auth_session_cookie,
    clear_oauth_state_cookie,
    read_auth_session_cookie,
    read_oauth_state_cookie,
    set_auth_session_cookie,
    set_oauth_state_cookie,
)


def test_set_auth_session_cookie_uses_shared_policy() -> None:
    response = Response()

    set_auth_session_cookie(response, "session-token", settings)

    cookie_headers = response.headers.getlist("set-cookie")
    assert len(cookie_headers) == 1
    cookie_header = cookie_headers[0]
    assert f"{settings.AUTH_SESSION_COOKIE_NAME}=session-token" in cookie_header
    assert "HttpOnly" in cookie_header
    assert f"Path={settings.AUTH_SESSION_COOKIE_PATH}" in cookie_header


def test_clear_auth_session_cookie_uses_shared_cookie_name() -> None:
    response = Response()

    clear_auth_session_cookie(response, settings)

    cookie_headers = response.headers.getlist("set-cookie")
    assert len(cookie_headers) == 1
    assert settings.AUTH_SESSION_COOKIE_NAME in cookie_headers[0]
    assert "Max-Age=0" in cookie_headers[0]


def test_read_auth_session_cookie_returns_configured_cookie_value() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [
                (
                    b"cookie",
                    f"{settings.AUTH_SESSION_COOKIE_NAME}=session-123".encode("utf-8"),
                )
            ],
        }
    )

    assert read_auth_session_cookie(request, settings) == "session-123"


def test_set_oauth_state_cookie_uses_scoped_shared_policy() -> None:
    response = Response()

    set_oauth_state_cookie(response, "oauth-nonce", settings)

    cookie_headers = response.headers.getlist("set-cookie")
    assert len(cookie_headers) == 1
    cookie_header = cookie_headers[0]
    assert f"{settings.AUTH_OAUTH_STATE_COOKIE_NAME}=oauth-nonce" in cookie_header
    assert "HttpOnly" in cookie_header
    assert f"Path={settings.AUTH_OAUTH_STATE_COOKIE_PATH}" in cookie_header
    assert "SameSite=lax" in cookie_header


def test_clear_oauth_state_cookie_uses_shared_cookie_name() -> None:
    response = Response()

    clear_oauth_state_cookie(response, settings)

    cookie_headers = response.headers.getlist("set-cookie")
    assert len(cookie_headers) == 1
    assert settings.AUTH_OAUTH_STATE_COOKIE_NAME in cookie_headers[0]
    assert "Max-Age=0" in cookie_headers[0]


def test_read_oauth_state_cookie_returns_configured_cookie_value() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": settings.AUTH_OAUTH_STATE_COOKIE_PATH,
            "query_string": b"",
            "headers": [
                (
                    b"cookie",
                    f"{settings.AUTH_OAUTH_STATE_COOKIE_NAME}=oauth-state-123".encode(
                        "utf-8"
                    ),
                )
            ],
        }
    )

    assert read_oauth_state_cookie(request, settings) == "oauth-state-123"
