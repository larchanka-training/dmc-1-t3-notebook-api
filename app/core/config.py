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

    SESSION_COOKIE_NAME: str = "session"
    SESSION_SECRET_KEY: str = "change-me-in-production"
    SESSION_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 7
    SESSION_COOKIE_SECURE: bool | None = None

    OTP_EXPIRES_SECONDS: int = 300
    OTP_MAX_ATTEMPTS: int = 5
    OTP_REQUEST_RATE_LIMIT: int = 5
    OTP_REQUEST_RATE_WINDOW_SECONDS: int = 900
    OTP_VERIFY_RATE_LIMIT: int = 20
    OTP_VERIFY_RATE_WINDOW_SECONDS: int = 900

    FRONTEND_URL: str = "http://localhost:3000"
    OAUTH_NAME_APPLICATION_ID: str = ""
    OAUTH_NAME_SECRET_KEY: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

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

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def expose_dev_otp(self) -> bool:
        return self.is_development

    @property
    def session_cookie_secure(self) -> bool:
        if self.SESSION_COOKIE_SECURE is not None:
            return self.SESSION_COOKIE_SECURE
        return self.ENVIRONMENT != "development"

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.OAUTH_NAME_APPLICATION_ID and self.OAUTH_NAME_SECRET_KEY)


settings = Settings()


def get_settings() -> Settings:
    """
    Dependency provider for application configuration.
    Injects settings via FastAPI Depends to prevent global state tight-coupling.
    """
    return settings
