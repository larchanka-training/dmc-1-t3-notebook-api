from urllib.parse import urlencode

import httpx

from app.core.config import Settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuthClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.settings.OAUTH_NAME_APPLICATION_ID,
            "redirect_uri": self.settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        payload = {
            "code": code,
            "client_id": self.settings.OAUTH_NAME_APPLICATION_ID,
            "client_secret": self.settings.OAUTH_NAME_SECRET_KEY,
            "redirect_uri": self.settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(GOOGLE_TOKEN_URL, data=payload)
            response.raise_for_status()
            return response.json()

    def fetch_user_info(self, access_token: str) -> dict:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
