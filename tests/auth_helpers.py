from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from fastapi import status

from app.core.config import settings


@dataclass(slots=True)
class AuthenticatedTestContext:
    client: httpx.AsyncClient
    email: str
    user: dict[str, Any]
    authenticated_at: str


def make_auth_test_email(prefix: str = "auth-user") -> str:
    return f"{prefix}-{uuid4().hex[:12]}@example.com"


async def request_otp(
    client: httpx.AsyncClient,
    email: str,
) -> dict[str, object]:
    response = await client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()


async def authenticate_via_email_otp(
    client: httpx.AsyncClient,
    email: str | None = None,
) -> AuthenticatedTestContext:
    normalized_email = email or make_auth_test_email()
    otp_payload = await request_otp(client, normalized_email)
    dev_otp = otp_payload.get("dev_otp")
    assert isinstance(dev_otp, str) and dev_otp, (
        "Email OTP auth test helper requires dev OTP support in the active test "
        "configuration."
    )

    response = await client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={
            "challenge_id": otp_payload["challenge_id"],
            "otp_code": dev_otp,
        },
    )
    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    return AuthenticatedTestContext(
        client=client,
        email=normalized_email,
        user=payload["user"],
        authenticated_at=payload["authenticated_at"],
    )
