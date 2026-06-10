from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.auth.models import OtpChallenge, Session, User
from tests.auth_helpers import request_otp


async def test_verify_otp_creates_user_session_and_cookie(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    request_payload = await request_otp(client, "verify@example.com")

    response = await client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={
            "challenge_id": request_payload["challenge_id"],
            "otp_code": request_payload["dev_otp"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["user"]["email"] == "verify@example.com"
    assert payload["user"]["display_name"] is None
    assert payload["authenticated_at"].endswith("Z")

    set_cookie_header = response.headers["set-cookie"]
    assert f"{settings.AUTH_SESSION_COOKIE_NAME}=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "Path=/" in set_cookie_header
    assert f"SameSite={settings.AUTH_SESSION_COOKIE_SAMESITE}" in set_cookie_header
    if settings.AUTH_SESSION_COOKIE_SECURE:
        assert "Secure" in set_cookie_header

    user = await db_session.scalar(select(User).where(User.email == "verify@example.com"))
    assert user is not None

    challenge = await db_session.scalar(
        select(OtpChallenge).where(
            OtpChallenge.id == UUID(str(request_payload["challenge_id"]))
        )
    )
    assert challenge is not None
    assert challenge.consumed_at is not None

    session = await db_session.scalar(select(Session).where(Session.user_id == user.id))
    assert session is not None
    assert session.revoked_at is None


async def test_verify_otp_reuses_existing_user(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    existing_user = User(email="existing@example.com")
    db_session.add(existing_user)
    await db_session.commit()

    request_payload = await request_otp(client, "existing@example.com")

    response = await client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={
            "challenge_id": request_payload["challenge_id"],
            "otp_code": request_payload["dev_otp"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user"]["id"] == str(existing_user.id)

    users = (await db_session.scalars(select(User).where(User.email == "existing@example.com"))).all()
    assert len(users) == 1


async def test_verify_otp_returns_401_for_unknown_challenge(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={
            "challenge_id": str(uuid4()),
            "otp_code": "123456",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": {
            "code": "otp_challenge_not_found",
            "message": "The OTP challenge was not found.",
        }
    }


async def test_verify_otp_returns_401_for_invalid_otp_and_increments_attempts(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    request_payload = await request_otp(client, "invalid@example.com")

    response = await client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={
            "challenge_id": request_payload["challenge_id"],
            "otp_code": "000000",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": {
            "code": "otp_invalid",
            "message": "The provided OTP code is invalid.",
        }
    }

    challenge = await db_session.scalar(
        select(OtpChallenge).where(
            OtpChallenge.id == UUID(str(request_payload["challenge_id"]))
        )
    )
    assert challenge is not None
    assert challenge.attempt_count == 1
    assert challenge.consumed_at is None


async def test_verify_otp_returns_401_for_expired_challenge(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    request_payload = await request_otp(client, "expired@example.com")
    challenge = await db_session.scalar(
        select(OtpChallenge).where(
            OtpChallenge.id == UUID(str(request_payload["challenge_id"]))
        )
    )
    assert challenge is not None
    challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    response = await client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={
            "challenge_id": request_payload["challenge_id"],
            "otp_code": request_payload["dev_otp"],
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": {
            "code": "otp_expired",
            "message": "The OTP challenge has expired.",
        }
    }


async def test_verify_otp_returns_409_for_consumed_challenge(
    client: httpx.AsyncClient,
) -> None:
    request_payload = await request_otp(client, "consumed@example.com")
    first = await client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={
            "challenge_id": request_payload["challenge_id"],
            "otp_code": request_payload["dev_otp"],
        },
    )
    second = await client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={
            "challenge_id": request_payload["challenge_id"],
            "otp_code": request_payload["dev_otp"],
        },
    )

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_409_CONFLICT
    assert second.json() == {
        "error": {
            "code": "otp_challenge_consumed",
            "message": "The OTP challenge has already been used.",
        }
    }


async def test_verify_otp_returns_429_when_attempt_limit_is_exhausted(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    request_payload = await request_otp(client, "attempts@example.com")
    challenge = await db_session.scalar(
        select(OtpChallenge).where(
            OtpChallenge.id == UUID(str(request_payload["challenge_id"]))
        )
    )
    assert challenge is not None
    challenge.attempt_count = challenge.max_attempts - 1
    await db_session.commit()

    response = await client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={
            "challenge_id": request_payload["challenge_id"],
            "otp_code": "000000",
        },
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.json() == {
        "error": {
            "code": "otp_attempt_limit_exceeded",
            "message": "Too many OTP attempts. Request a new code and try again.",
        }
    }

    challenge = await db_session.scalar(
        select(OtpChallenge).where(
            OtpChallenge.id == UUID(str(request_payload["challenge_id"]))
        )
    )
    assert challenge is not None
    assert challenge.attempt_count == challenge.max_attempts
