import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings


def _request_otp(client: TestClient, email: str = "user@example.com") -> dict:
    response = client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()


def _verify_otp(
    client: TestClient,
    *,
    challenge_id: str,
    otp_code: str,
) -> dict:
    response = client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"challenge_id": challenge_id, "otp_code": otp_code},
    )
    return response.json(), response


def test_request_otp_returns_challenge_and_dev_otp_in_development(
    client: TestClient,
) -> None:
    payload = _request_otp(client)

    assert payload["challenge_id"].startswith("otp_ch_")
    assert payload["expires_in_seconds"] == settings.OTP_EXPIRES_SECONDS
    assert payload["dev_otp"] is not None
    assert len(payload["dev_otp"]) == 6


def test_verify_otp_establishes_session_and_returns_user(client: TestClient) -> None:
    challenge = _request_otp(client, email="verify@example.com")
    payload, response = _verify_otp(
        client,
        challenge_id=challenge["challenge_id"],
        otp_code=challenge["dev_otp"],
    )

    assert response.status_code == status.HTTP_200_OK
    assert payload["user"]["email"] == "verify@example.com"
    assert "authenticated_at" in payload
    assert settings.SESSION_COOKIE_NAME in response.cookies


def test_session_returns_authenticated_user_after_verify(client: TestClient) -> None:
    challenge = _request_otp(client, email="session@example.com")
    _, verify_response = _verify_otp(
        client,
        challenge_id=challenge["challenge_id"],
        otp_code=challenge["dev_otp"],
    )

    session_response = client.get(
        f"{settings.API_V1_STR}/auth/session",
        cookies=verify_response.cookies,
    )

    assert session_response.status_code == status.HTTP_200_OK
    payload = session_response.json()
    assert payload["authenticated"] is True
    assert payload["user"]["email"] == "session@example.com"


def test_session_returns_anonymous_without_cookie(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/auth/session")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["authenticated"] is False
    assert payload["user"] is None


def test_logout_invalidates_session(client: TestClient) -> None:
    challenge = _request_otp(client, email="logout@example.com")
    _, verify_response = _verify_otp(
        client,
        challenge_id=challenge["challenge_id"],
        otp_code=challenge["dev_otp"],
    )

    logout_response = client.post(
        f"{settings.API_V1_STR}/auth/logout",
        cookies=verify_response.cookies,
    )
    assert logout_response.status_code == status.HTTP_200_OK
    assert logout_response.json()["logged_out"] is True

    session_response = client.get(
        f"{settings.API_V1_STR}/auth/session",
        cookies=verify_response.cookies,
    )
    assert session_response.json()["authenticated"] is False


def test_verify_otp_rejects_invalid_code(client: TestClient) -> None:
    challenge = _request_otp(client, email="invalid@example.com")
    payload, response = _verify_otp(
        client,
        challenge_id=challenge["challenge_id"],
        otp_code="000000",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert payload["error"]["code"] == "otp_invalid"


def test_verify_otp_rejects_consumed_challenge(client: TestClient) -> None:
    challenge = _request_otp(client, email="consumed@example.com")
    _verify_otp(
        client,
        challenge_id=challenge["challenge_id"],
        otp_code=challenge["dev_otp"],
    )

    payload, response = _verify_otp(
        client,
        challenge_id=challenge["challenge_id"],
        otp_code=challenge["dev_otp"],
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert payload["error"]["code"] == "otp_challenge_not_found"


def test_request_otp_normalizes_email(client: TestClient) -> None:
    upper = _request_otp(client, email="  Normalize@Example.COM  ")
    lower = _request_otp(client, email="normalize@example.com")

    assert upper["challenge_id"] != lower["challenge_id"]


def test_request_otp_rejects_invalid_email(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": "not-an-email"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_google_start_returns_not_configured_without_credentials(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OAUTH_NAME_APPLICATION_ID", "")
    monkeypatch.setattr(settings, "OAUTH_NAME_SECRET_KEY", "")

    response = client.get(
        f"{settings.API_V1_STR}/auth/google/start",
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == "google_oauth_not_configured"
