import os
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _load_aws_secret() -> None:
    """
    When AWS_APP_SECRET_ARN is present the application is running on AWS.
    Fetch the single ini-format secret and inject every KEY=VALUE pair into
    os.environ so that pydantic-settings picks them up with highest priority.
    Values already set in the environment are not overwritten (setdefault).
    """
    secret_arn = os.environ.get("AWS_APP_SECRET_ARN")
    if not secret_arn:
        return

    import boto3  # lazy import – not required for local development

    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    secret_text: str = response["SecretString"]

    for raw_line in secret_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip optional surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


_load_aws_secret()


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
    GIT_BRANCH: str = "unknown"
    BUILD_TIME: str = "unknown"

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
    AUTH_DEBUG_MODE: bool = False

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
    AI_PROVIDER_ENABLED: bool = False
    AI_PROVIDER_NAME: Literal["bedrock"] = "bedrock"
    AI_PROVIDER_MODEL: str = "anthropic.claude-3-haiku"
    AI_BEDROCK_REGION: str = ""
    AI_BEDROCK_TIMEOUT_SECONDS: float = 20.0
    AI_BEDROCK_MAX_RETRIES: int = 1

    SES_FROM_EMAIL: str = "noreply@t3.jsnb.org"
    SES_REGION: str = "eu-north-1"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("AI_BEDROCK_REGION", "AI_PROVIDER_MODEL", mode="before")
    @classmethod
    def strip_ai_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
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

    @property
    def ses_email_enabled(self) -> bool:
        return bool(self.SES_FROM_EMAIL.strip())

    @property
    def ai_bedrock_runtime_configured(self) -> bool:
        return bool(
            self.AI_PROVIDER_ENABLED
            and self.AI_PROVIDER_NAME == "bedrock"
            and self.AI_BEDROCK_REGION
            and self.AI_PROVIDER_MODEL
            and self.AI_BEDROCK_TIMEOUT_SECONDS > 0
            and self.AI_BEDROCK_MAX_RETRIES >= 0
        )

    @property
    def ai_bedrock_runtime_missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.AI_PROVIDER_ENABLED:
            missing.append("AI_PROVIDER_ENABLED")
        if self.AI_PROVIDER_NAME != "bedrock":
            missing.append("AI_PROVIDER_NAME")
        if not self.AI_BEDROCK_REGION:
            missing.append("AI_BEDROCK_REGION")
        if not self.AI_PROVIDER_MODEL:
            missing.append("AI_PROVIDER_MODEL")
        if self.AI_BEDROCK_TIMEOUT_SECONDS <= 0:
            missing.append("AI_BEDROCK_TIMEOUT_SECONDS")
        if self.AI_BEDROCK_MAX_RETRIES < 0:
            missing.append("AI_BEDROCK_MAX_RETRIES")
        return missing


settings = Settings()


def get_settings() -> Settings:
    """
    Dependency provider for application configuration.
    Injects settings via FastAPI Depends to prevent global state tight-coupling.
    """
    return settings
