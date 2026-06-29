from __future__ import annotations

from app.core.config import Settings
from app.features.auth.dependencies import get_otp_delivery_gateway
from app.integrations.email_delivery import (
    LoggingOtpDeliveryGateway,
    SesOtpDeliveryGateway,
)


def test_get_otp_delivery_gateway_uses_logging_gateway_in_dev_with_dev_otp() -> None:
    settings = Settings(
        ENVIRONMENT="development",
        AUTH_RETURN_DEV_OTP=True,
        SES_FROM_EMAIL="noreply@example.com",
        SES_REGION="eu-north-1",
    )

    gateway = get_otp_delivery_gateway(settings=settings)

    assert isinstance(gateway, LoggingOtpDeliveryGateway)


def test_get_otp_delivery_gateway_uses_ses_when_dev_otp_is_disabled() -> None:
    settings = Settings(
        ENVIRONMENT="development",
        AUTH_RETURN_DEV_OTP=False,
        SES_FROM_EMAIL="noreply@example.com",
        SES_REGION="eu-north-1",
    )

    gateway = get_otp_delivery_gateway(settings=settings)

    assert isinstance(gateway, SesOtpDeliveryGateway)


def test_get_otp_delivery_gateway_uses_ses_outside_dev_when_email_is_configured() -> None:
    settings = Settings(
        ENVIRONMENT="production",
        AUTH_RETURN_DEV_OTP=True,
        SES_FROM_EMAIL="noreply@example.com",
        SES_REGION="eu-north-1",
    )

    gateway = get_otp_delivery_gateway(settings=settings)

    assert isinstance(gateway, SesOtpDeliveryGateway)
