from __future__ import annotations

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.auth.models import OAuthAccount, OAuthState, User


def _configure_google_oauth() -> None:
    settings.GOOGLE_OAUTH_CLIENT_ID = "test-google-client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "test-google-client-secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "https://api.notebook.com:8443/api/v1/auth/google/callback"
    settings.GOOGLE_OAUTH_SUCCESS_REDIRECT_URL = "https://notebook.com:8443/auth/success"
    settings.GOOGLE_OAUTH_ERROR_REDIRECT_URL = "https://notebook.com:8443/auth/error"


def _extract_state(location: str) -> str:
    return parse_qs(urlparse(location).query)["state"][0]


async def _start_google_oauth(client: httpx.AsyncClient) -> httpx.Response:
    _configure_google_oauth()
    response = await client.get(
        f"{settings.API_V1_STR}/auth/google/start",
        follow_redirects=False,
    )
    assert response.status_code == status.HTTP_302_FOUND
    return response


async def test_google_start_redirects_to_provider_and_sets_short_lived_state_cookie(
    client: httpx.AsyncClient,
) -> None:
    response = await _start_google_oauth(client)

    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert query["client_id"] == [settings.GOOGLE_OAUTH_CLIENT_ID]
    assert query["redirect_uri"] == [settings.GOOGLE_OAUTH_REDIRECT_URI]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid email profile"]
    assert query["state"]

    set_cookie_header = response.headers["set-cookie"]
    assert f"{settings.AUTH_OAUTH_STATE_COOKIE_NAME}=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert f"Path={settings.AUTH_OAUTH_STATE_COOKIE_PATH}" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header


@patch(
    "app.integrations.google_oauth.client.GoogleOAuthClient.fetch_user_info",
    new_callable=AsyncMock,
)
@patch(
    "app.integrations.google_oauth.client.GoogleOAuthClient.exchange_code",
    new_callable=AsyncMock,
)
async def test_google_callback_success_creates_session_and_supports_session_bootstrap(
    mock_exchange_code: AsyncMock,
    mock_fetch_user_info: AsyncMock,
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    start_response = await _start_google_oauth(client)
    state = _extract_state(start_response.headers["location"])

    mock_exchange_code.return_value = {"access_token": "oauth-access-token"}
    mock_fetch_user_info.return_value = type(
        "Identity",
        (),
        {
            "subject": "google-subject-001",
            "email": "oauth-success@example.com",
            "email_verified": True,
            "display_name": "OAuth Success",
        },
    )()

    response = await client.get(
        f"{settings.API_V1_STR}/auth/google/callback",
        params={"code": "google-auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == settings.GOOGLE_OAUTH_SUCCESS_REDIRECT_URL

    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(
        header.startswith(f"{settings.AUTH_SESSION_COOKIE_NAME}=")
        and "HttpOnly" in header
        for header in set_cookie_headers
    )
    assert any(
        header.startswith(f"{settings.AUTH_OAUTH_STATE_COOKIE_NAME}=")
        and "Max-Age=0" in header
        for header in set_cookie_headers
    )

    oauth_user = await db_session.scalar(
        select(User).where(User.email == "oauth-success@example.com")
    )
    assert oauth_user is not None

    oauth_account = await db_session.scalar(
        select(OAuthAccount).where(OAuthAccount.provider_subject == "google-subject-001")
    )
    assert oauth_account is not None
    assert oauth_account.user_id == oauth_user.id

    session_response = await client.get(f"{settings.API_V1_STR}/auth/session")
    assert session_response.status_code == status.HTTP_200_OK
    assert session_response.json() == {
        "authenticated": True,
        "user": {
            "id": str(oauth_user.id),
            "email": "oauth-success@example.com",
            "display_name": "OAuth Success",
        },
    }


@patch(
    "app.integrations.google_oauth.client.GoogleOAuthClient.fetch_user_info",
    new_callable=AsyncMock,
)
@patch(
    "app.integrations.google_oauth.client.GoogleOAuthClient.exchange_code",
    new_callable=AsyncMock,
)
async def test_google_callback_provider_denial_redirects_with_stable_error_code(
    mock_exchange_code: AsyncMock,
    mock_fetch_user_info: AsyncMock,
    client: httpx.AsyncClient,
) -> None:
    start_response = await _start_google_oauth(client)
    state = _extract_state(start_response.headers["location"])

    response = await client.get(
        f"{settings.API_V1_STR}/auth/google/callback",
        params={"error": "access_denied", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == (
        f"{settings.GOOGLE_OAUTH_ERROR_REDIRECT_URL}?code=oauth_access_denied"
    )
    assert mock_exchange_code.await_count == 0
    assert mock_fetch_user_info.await_count == 0
    assert "Max-Age=0" in response.headers["set-cookie"]

    session_response = await client.get(f"{settings.API_V1_STR}/auth/session")
    assert session_response.json() == {"authenticated": False, "user": None}


async def test_google_callback_invalid_state_redirects_with_controlled_error(
    client: httpx.AsyncClient,
) -> None:
    await _start_google_oauth(client)

    response = await client.get(
        f"{settings.API_V1_STR}/auth/google/callback",
        params={"code": "google-auth-code", "state": "invalid.state"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == (
        f"{settings.GOOGLE_OAUTH_ERROR_REDIRECT_URL}?code=oauth_state_invalid"
    )
    assert "Max-Age=0" in response.headers["set-cookie"]


async def test_google_callback_expired_state_redirects_with_controlled_error(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    start_response = await _start_google_oauth(client)
    state = _extract_state(start_response.headers["location"])

    oauth_state = await db_session.scalar(select(OAuthState))
    assert oauth_state is not None
    oauth_state.expires_at = oauth_state.created_at
    await db_session.flush()

    response = await client.get(
        f"{settings.API_V1_STR}/auth/google/callback",
        params={"code": "google-auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == (
        f"{settings.GOOGLE_OAUTH_ERROR_REDIRECT_URL}?code=oauth_state_expired"
    )


@patch(
    "app.integrations.google_oauth.client.GoogleOAuthClient.exchange_code",
    new_callable=AsyncMock,
)
async def test_google_callback_exchange_failure_redirects_with_controlled_error(
    mock_exchange_code: AsyncMock,
    client: httpx.AsyncClient,
) -> None:
    start_response = await _start_google_oauth(client)
    state = _extract_state(start_response.headers["location"])

    mock_exchange_code.side_effect = httpx.HTTPError("token exchange failed")

    response = await client.get(
        f"{settings.API_V1_STR}/auth/google/callback",
        params={"code": "google-auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == (
        f"{settings.GOOGLE_OAUTH_ERROR_REDIRECT_URL}?code=oauth_exchange_failed"
    )


@patch(
    "app.integrations.google_oauth.client.GoogleOAuthClient.fetch_user_info",
    new_callable=AsyncMock,
)
@patch(
    "app.integrations.google_oauth.client.GoogleOAuthClient.exchange_code",
    new_callable=AsyncMock,
)
async def test_google_callback_auto_links_existing_user_by_verified_email(
    mock_exchange_code: AsyncMock,
    mock_fetch_user_info: AsyncMock,
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    existing_user = User(email="existing-link@example.com", display_name=None)
    db_session.add(existing_user)
    await db_session.flush()

    start_response = await _start_google_oauth(client)
    state = _extract_state(start_response.headers["location"])

    mock_exchange_code.return_value = {"access_token": "oauth-access-token"}
    mock_fetch_user_info.return_value = type(
        "Identity",
        (),
        {
            "subject": "google-subject-autolink",
            "email": "existing-link@example.com",
            "email_verified": True,
            "display_name": "Existing Link",
        },
    )()

    response = await client.get(
        f"{settings.API_V1_STR}/auth/google/callback",
        params={"code": "google-auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == settings.GOOGLE_OAUTH_SUCCESS_REDIRECT_URL

    users = (
        await db_session.scalars(
            select(User).where(User.email == "existing-link@example.com")
        )
    ).all()
    assert len(users) == 1

    oauth_account = await db_session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider_subject == "google-subject-autolink"
        )
    )
    assert oauth_account is not None
    assert oauth_account.user_id == existing_user.id
