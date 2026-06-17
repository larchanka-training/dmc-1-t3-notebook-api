from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "Enterprise Backend API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    DATABASE_URL: str = "postgresql+psycopg://admin:admin123@postgres:5432/wiki"
    BACKEND_CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "https://localhost:8443",
            "http://notebook.com:8080",
            "https://notebook.com:8443",
        ]
    )
    AUTH_OTP_TTL_SECONDS: int = 300
    AUTH_OTP_MAX_ATTEMPTS: int = 5
    AUTH_OTP_REQUEST_COOLDOWN_SECONDS: int = 60
    AUTH_OTP_CODE_LENGTH: int = 6
    AUTH_OTP_HASH_SECRET: str = "development-auth-otp-secret"
    AUTH_RETURN_DEV_OTP: bool = True

    AUTH_SESSION_TTL_SECONDS: int = 60 * 60 * 24 * 30
    AUTH_SESSION_COOKIE_NAME: str = "notebook_session"
    AUTH_SESSION_COOKIE_SECURE: bool = True
    AUTH_SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    AUTH_SESSION_COOKIE_PATH: str = "/"
    AUTH_SESSION_COOKIE_DOMAIN: str | None = None
    AUTH_SESSION_HASH_SECRET: str = "development-auth-session-secret"
    AUTH_OAUTH_STATE_TTL_SECONDS: int = 300
    AUTH_OAUTH_STATE_COOKIE_NAME: str = "notebook_oauth_state"
    AUTH_OAUTH_STATE_COOKIE_PATH: str = "/api/v1/auth/google"
    AUTH_OAUTH_STATE_COOKIE_DOMAIN: str | None = None
    AUTH_OAUTH_STATE_SIGNING_SECRET: str = "development-auth-oauth-state-secret"

    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = "https://api.notebook.com:8443/api/v1/auth/google/callback"
    GOOGLE_OAUTH_SUCCESS_REDIRECT_URL: str = "https://notebook.com:8443/"
    GOOGLE_OAUTH_ERROR_REDIRECT_URL: str = "https://notebook.com:8443/auth/error"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def auth_dev_otp_enabled(self) -> bool:
        return self.ENVIRONMENT == "development" and self.AUTH_RETURN_DEV_OTP

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(
            self.GOOGLE_OAUTH_CLIENT_ID.strip()
            and self.GOOGLE_OAUTH_CLIENT_SECRET.strip()
            and self.GOOGLE_OAUTH_REDIRECT_URI.strip()
        )


settings = Settings()


def get_settings() -> Settings:
    """
    Dependency provider for application configuration.
    Injects settings via FastAPI Depends to prevent global state tight-coupling.
    """
    return settings
