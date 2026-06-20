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


class SesOtpDeliveryGateway(OtpDeliveryGateway):
    def __init__(self, from_email: str, region: str) -> None:
        self._from_email = from_email
        self._region = region

    async def send_otp(self, message: OtpDeliveryMessage) -> None:
        import boto3  # lazy import – not required for local development

        expires_minutes = message.expires_in_seconds // 60
        subject = "Your login code"
        body_text = (
            f"Your login code is: {message.otp_code}\n\n"
            f"It expires in {expires_minutes} minute(s). Do not share it with anyone."
        )

        client = boto3.client("ses", region_name=self._region)
        client.send_email(
            Source=self._from_email,
            Destination={"ToAddresses": [message.email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
            },
        )
        logger.info(
            "SES OTP email sent to %s challenge=%s",
            message.email,
            message.challenge_id,
        )

