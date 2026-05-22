import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_SESSION_SECRET_KEY, Settings


def test_production_rejects_default_session_secret() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SESSION_SECRET_KEY=DEFAULT_SESSION_SECRET_KEY,
            OTP_EMAIL_DELIVERY_ENABLED=True,
        )

    assert "SESSION_SECRET_KEY" in str(exc_info.value)


def test_production_requires_otp_delivery() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SESSION_SECRET_KEY="a-secure-production-secret-key",
            EXPOSE_DEV_OTP=False,
            OTP_EMAIL_DELIVERY_ENABLED=False,
        )

    assert "OTP delivery" in str(exc_info.value)


def test_production_accepts_valid_configuration() -> None:
    settings = Settings(
        ENVIRONMENT="production",
        SESSION_SECRET_KEY="a-secure-production-secret-key",
        OTP_EMAIL_DELIVERY_ENABLED=True,
    )

    assert settings.otp_delivery_available is True
