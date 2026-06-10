from __future__ import annotations

import logging
from dataclasses import dataclass


logger = logging.getLogger("app.integrations.email_delivery")


@dataclass(slots=True)
class OtpDeliveryMessage:
    email: str
    otp_code: str
    challenge_id: str
    expires_in_seconds: int


class OtpDeliveryGateway:
    async def send_otp(self, message: OtpDeliveryMessage) -> None:
        raise NotImplementedError


class LoggingOtpDeliveryGateway(OtpDeliveryGateway):
    async def send_otp(self, message: OtpDeliveryMessage) -> None:
        logger.info(
            "Stub OTP delivery prepared for %s challenge=%s expires_in=%s",
            message.email,
            message.challenge_id,
            message.expires_in_seconds,
        )

