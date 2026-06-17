from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import Settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@dataclass(slots=True)
class GoogleOAuthIdentity:
    subject: str
    email: str | None
    email_verified: bool
    display_name: str | None


class GoogleOAuthClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": self.settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        payload = {
            "code": code,
            "client_id": self.settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": self.settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": self.settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=payload)
            response.raise_for_status()
            return response.json()

    async def fetch_user_info(self, access_token: str) -> GoogleOAuthIdentity:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            payload = response.json()
            return GoogleOAuthIdentity(
                subject=str(payload.get("sub") or ""),
                email=payload.get("email"),
                email_verified=bool(payload.get("email_verified")),
                display_name=payload.get("name"),
            )
