from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import httpx
from fastapi import status

from app.core.config import settings
from app.features.auth.models import Session, User
from tests.auth_helpers import authenticate_via_email_otp


async def test_session_returns_anonymous_shape_without_cookie(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"{settings.API_V1_STR}/auth/session")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "authenticated": False,
        "user": None,
    }


async def test_session_returns_authenticated_user_for_active_session(
    client: httpx.AsyncClient,
) -> None:
    auth_context = await authenticate_via_email_otp(client, "session@example.com")

    response = await client.get(f"{settings.API_V1_STR}/auth/session")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "authenticated": True,
        "user": auth_context.user,
    }


async def test_session_returns_anonymous_shape_for_invalid_cookie(
    client: httpx.AsyncClient,
) -> None:
    client.cookies.set(settings.AUTH_SESSION_COOKIE_NAME, "invalid-session-token")

    response = await client.get(f"{settings.API_V1_STR}/auth/session")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "authenticated": False,
        "user": None,
    }


async def test_logout_revokes_session_clears_cookie_and_resets_session_state(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    auth_context = await authenticate_via_email_otp(client, "logout@example.com")

    response = await client.post(f"{settings.API_V1_STR}/auth/logout")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"logged_out": True}

    set_cookie_header = response.headers["set-cookie"]
    assert f"{settings.AUTH_SESSION_COOKIE_NAME}=" in set_cookie_header
    assert "Max-Age=0" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert f"Path={settings.AUTH_SESSION_COOKIE_PATH}" in set_cookie_header
    assert f"SameSite={settings.AUTH_SESSION_COOKIE_SAMESITE}" in set_cookie_header
    if settings.AUTH_SESSION_COOKIE_SECURE:
        assert "Secure" in set_cookie_header

    user = await db_session.scalar(
        select(User).where(User.email == auth_context.email)
    )
    assert user is not None

    auth_session = await db_session.scalar(
        select(Session).where(Session.user_id == user.id)
    )
    assert auth_session is not None
    assert auth_session.revoked_at is not None

    session_response = await client.get(f"{settings.API_V1_STR}/auth/session")
    assert session_response.status_code == status.HTTP_200_OK
    assert session_response.json() == {
        "authenticated": False,
        "user": None,
    }


async def test_logout_is_idempotent_for_repeated_calls(
    client: httpx.AsyncClient,
) -> None:
    await authenticate_via_email_otp(client, "repeat-logout@example.com")

    first = await client.post(f"{settings.API_V1_STR}/auth/logout")
    second = await client.post(f"{settings.API_V1_STR}/auth/logout")

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert first.json() == {"logged_out": True}
    assert second.json() == {"logged_out": True}


async def test_logout_is_controlled_for_missing_or_invalid_cookie(
    client: httpx.AsyncClient,
) -> None:
    client.cookies.set(settings.AUTH_SESSION_COOKIE_NAME, "invalid-session-token")

    response = await client.post(f"{settings.API_V1_STR}/auth/logout")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"logged_out": True}
    assert "Max-Age=0" in response.headers["set-cookie"]
