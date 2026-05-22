import logging

logger = logging.getLogger(__name__)


def send_otp_email(email: str, otp_code: str) -> None:
    """
    Deliver OTP via the configured email provider.

    Version 1 uses a no-op stub outside development; production should wire
    a real provider integration here.
    """
    logger.info("OTP email delivery queued", extra={"email": email})
