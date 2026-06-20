from __future__ import annotations

import httpx
import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.auth.models import OtpChallenge


async def test_request_otp_returns_challenge_and_dev_otp(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    response = await client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": "  Test.User@Example.com  "},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["challenge_id"]
    assert payload["expires_in_seconds"] == settings.AUTH_OTP_TTL_SECONDS
    assert payload["dev_otp"].isdigit()
    assert len(payload["dev_otp"]) == settings.AUTH_OTP_CODE_LENGTH

    challenge = await db_session.scalar(select(OtpChallenge))
    assert challenge is not None
    assert challenge.email == "test.user@example.com"
    assert challenge.otp_code_hash != payload["dev_otp"]
    assert len(challenge.otp_code_hash) == 64
    assert challenge.max_attempts == settings.AUTH_OTP_MAX_ATTEMPTS


async def test_request_otp_returns_422_for_invalid_payload(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": "invalid-email"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_request_otp_hides_dev_otp_when_config_disables_it(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AUTH_RETURN_DEV_OTP", False)

    response = await client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": "prodlike@example.com"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert "dev_otp" not in response.json()


async def test_request_otp_returns_429_when_email_is_throttled(
    client: httpx.AsyncClient,
) -> None:
    first = await client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": "throttle@example.com"},
    )
    second = await client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": "throttle@example.com"},
    )

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert second.json() == {
        "error": {
            "code": "otp_request_rate_limited",
            "message": "Too many OTP requests. Try again later.",
        }
    }
