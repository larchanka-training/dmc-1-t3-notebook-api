import logging

logger = logging.getLogger(__name__)


def send_otp_email(email: str, otp_code: str) -> None:
    """
    Deliver OTP via the configured email provider.

    Call only when Settings.otp_delivery_available is true and
    OTP_EMAIL_DELIVERY_ENABLED is enabled. Production should replace this stub
    with a real provider integration.
    """
    logger.info("OTP email delivery queued", extra={"email": email})
