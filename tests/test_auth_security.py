from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import add_seconds, hash_value, utc_now
from app.features.auth.dependencies import get_client_ip
from app.features.auth.models import OtpChallenge
from app.features.auth.rate_limit import otp_request_limiter, otp_verify_limiter
from app.features.auth.service import AuthService


def _request_otp(client: TestClient, email: str = "user@example.com") -> dict:
    response = client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email},
    )
    return response.json(), response


def _verify_otp(
    client: TestClient,
    *,
    challenge_id: str,
    otp_code: str,
) -> tuple[dict, object]:
    response = client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"challenge_id": challenge_id, "otp_code": otp_code},
    )
    return response.json(), response


def test_staging_request_otp_without_delivery_returns_503(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "EXPOSE_DEV_OTP", False)
    monkeypatch.setattr(settings, "OTP_EMAIL_DELIVERY_ENABLED", False)

    payload, response = _request_otp(client, email="staging@example.com")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert payload["error"]["code"] == "otp_delivery_unavailable"


def test_staging_response_omits_dev_otp(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "EXPOSE_DEV_OTP", False)
    monkeypatch.setattr(settings, "OTP_EMAIL_DELIVERY_ENABLED", True)

    payload, response = _request_otp(client, email="staging-otp@example.com")

    assert response.status_code == status.HTTP_200_OK
    assert payload["dev_otp"] is None


def test_request_otp_rate_limited_by_email(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OTP_REQUEST_RATE_LIMIT", 2)
    email = "ratelimit@example.com"

    for _ in range(2):
        payload, response = _request_otp(client, email=email)
        assert response.status_code == status.HTTP_200_OK
        assert payload["challenge_id"].startswith("otp_ch_")

    payload, response = _request_otp(client, email=email)

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert payload["error"]["code"] == "otp_request_rate_limited"
    assert response.headers.get("Retry-After") is not None


def test_verify_otp_rejects_expired_challenge(
    client: TestClient,
    db: Session,
) -> None:
    challenge_payload, _ = _request_otp(client, email="expired@example.com")
    challenge = db.get(OtpChallenge, challenge_payload["challenge_id"])
    assert challenge is not None
    challenge.expires_at = add_seconds(utc_now(), -60)
    db.flush()

    payload, response = _verify_otp(
        client,
        challenge_id=challenge_payload["challenge_id"],
        otp_code=challenge_payload["dev_otp"],
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert payload["error"]["code"] == "otp_expired"


def test_verify_otp_locks_out_after_max_attempts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OTP_MAX_ATTEMPTS", 3)
    challenge_payload, _ = _request_otp(client, email="maxattempts@example.com")

    for _ in range(2):
        payload, response = _verify_otp(
            client,
            challenge_id=challenge_payload["challenge_id"],
            otp_code="000000",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert payload["error"]["code"] == "otp_invalid"

    payload, response = _verify_otp(
        client,
        challenge_id=challenge_payload["challenge_id"],
        otp_code="000000",
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert payload["error"]["code"] == "otp_attempt_limit_exceeded"


def test_session_returns_anonymous_for_expired_session(
    client: TestClient,
    db: Session,
) -> None:
    challenge_payload, _ = _request_otp(client, email="sess-exp@example.com")
    _, verify_response = _verify_otp(
        client,
        challenge_id=challenge_payload["challenge_id"],
        otp_code=challenge_payload["dev_otp"],
    )
    assert verify_response.status_code == status.HTTP_200_OK

    token = verify_response.cookies.get(settings.SESSION_COOKIE_NAME)
    assert token is not None

    auth_service = AuthService(db, settings)
    session = auth_service.repo.get_session_by_token_hash(
        hash_value(token, secret=settings.SESSION_SECRET_KEY)
    )
    assert session is not None
    session.expires_at = add_seconds(utc_now(), -60)
    db.commit()

    session_response = client.get(
        f"{settings.API_V1_STR}/auth/session",
        cookies=verify_response.cookies,
    )

    assert session_response.json()["authenticated"] is False


def test_get_client_ip_ignores_forwarded_without_trust_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)

    class FakeClient:
        host = "203.0.113.10"

    class FakeRequest:
        headers = {"x-forwarded-for": "198.51.100.1"}
        client = FakeClient()

    assert get_client_ip(FakeRequest(), settings) == "203.0.113.10"


def test_get_client_ip_uses_forwarded_when_trust_proxy_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)

    class FakeClient:
        host = "203.0.113.10"

    class FakeRequest:
        headers = {"x-forwarded-for": "198.51.100.1, 203.0.113.99"}
        client = FakeClient()

    assert get_client_ip(FakeRequest(), settings) == "198.51.100.1"


def _oauth_state_from_start_response(start_response: object) -> str:
    from urllib.parse import parse_qs, urlparse

    location = start_response.headers["location"]
    return parse_qs(urlparse(location).query)["state"][0]


@patch("app.integrations.google_oauth.client.GoogleOAuthClient.fetch_user_info")
@patch("app.integrations.google_oauth.client.GoogleOAuthClient.exchange_code")
def test_google_callback_rejects_unverified_email(
    mock_exchange_code: MagicMock,
    mock_fetch_user_info: MagicMock,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OAUTH_NAME_APPLICATION_ID", "test-client-id")
    monkeypatch.setattr(settings, "OAUTH_NAME_SECRET_KEY", "test-client-secret")

    start_response = client.get(
        f"{settings.API_V1_STR}/auth/google/start",
        follow_redirects=False,
    )
    assert start_response.status_code == status.HTTP_302_FOUND
    state = _oauth_state_from_start_response(start_response)

    mock_exchange_code.return_value = {"access_token": "token"}
    mock_fetch_user_info.return_value = {
        "sub": "google-user-1",
        "email": "oauth@example.com",
        "email_verified": False,
    }

    callback_response = client.get(
        f"{settings.API_V1_STR}/auth/google/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert callback_response.status_code == status.HTTP_302_FOUND
    assert "oauth_email_unverified" in callback_response.headers["location"]
    assert settings.SESSION_COOKIE_NAME not in callback_response.cookies


@patch("app.integrations.google_oauth.client.GoogleOAuthClient.fetch_user_info")
@patch("app.integrations.google_oauth.client.GoogleOAuthClient.exchange_code")
def test_google_callback_establishes_session_for_verified_email(
    mock_exchange_code: MagicMock,
    mock_fetch_user_info: MagicMock,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OAUTH_NAME_APPLICATION_ID", "test-client-id")
    monkeypatch.setattr(settings, "OAUTH_NAME_SECRET_KEY", "test-client-secret")

    start_response = client.get(
        f"{settings.API_V1_STR}/auth/google/start",
        follow_redirects=False,
    )
    assert start_response.status_code == status.HTTP_302_FOUND
    state = _oauth_state_from_start_response(start_response)

    mock_exchange_code.return_value = {"access_token": "token"}
    mock_fetch_user_info.return_value = {
        "sub": "google-user-2",
        "email": "verified-oauth@example.com",
        "email_verified": True,
    }

    callback_response = client.get(
        f"{settings.API_V1_STR}/auth/google/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert callback_response.status_code == status.HTTP_302_FOUND
    assert callback_response.headers["location"] == settings.FRONTEND_URL
    assert settings.SESSION_COOKIE_NAME in callback_response.cookies
