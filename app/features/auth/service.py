from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.features.auth.errors import (
    AuthRateLimitError,
    OtpAttemptLimitExceededError,
    OtpChallengeConsumedError,
    OtpChallengeNotFoundError,
    OtpExpiredError,
    OtpInvalidError,
)
from app.features.auth.models import OtpChallenge, Session, User
from app.features.auth.repository import AuthRepository
from app.integrations.email_delivery import OtpDeliveryGateway, OtpDeliveryMessage


@dataclass(slots=True)
class OtpRequestResult:
    challenge_id: str
    expires_in_seconds: int
    dev_otp: str | None


@dataclass(slots=True)
class OtpVerificationResult:
    user: User
    authenticated_at: datetime
    session_token: str
    session: Session


class AuthService:
    def __init__(
        self,
        *,
        repository: AuthRepository,
        settings: Settings,
        otp_delivery_gateway: OtpDeliveryGateway,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.otp_delivery_gateway = otp_delivery_gateway

    async def request_otp(self, *, email: str) -> OtpRequestResult:
        existing = await self.repository.get_recent_active_challenge_for_email(
            email=email,
            cooldown_seconds=self.settings.AUTH_OTP_REQUEST_COOLDOWN_SECONDS,
        )
        if existing is not None:
            raise AuthRateLimitError()

        otp_code = self._generate_numeric_otp()
        expires_in_seconds = self.settings.AUTH_OTP_TTL_SECONDS
        challenge = await self.repository.create_otp_challenge(
            email=email,
            otp_code_hash=self.hash_otp_code(otp_code),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
            max_attempts=self.settings.AUTH_OTP_MAX_ATTEMPTS,
        )

        await self.otp_delivery_gateway.send_otp(
            OtpDeliveryMessage(
                email=email,
                otp_code=otp_code,
                challenge_id=str(challenge.id),
                expires_in_seconds=expires_in_seconds,
            )
        )
        await self.repository.session.commit()

        return OtpRequestResult(
            challenge_id=str(challenge.id),
            expires_in_seconds=expires_in_seconds,
            dev_otp=otp_code if self.settings.auth_dev_otp_enabled else None,
        )

    async def get_or_create_user(self, *, email: str) -> User:
        user = await self.repository.get_user_by_email(email)
        if user is not None:
            return user
        return await self.repository.create_user(email=email)

    async def create_session_for_user(
        self,
        *,
        user_id: uuid.UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, Session]:
        session_token = secrets.token_urlsafe(32)
        auth_session = await self.repository.create_session(
            user_id=user_id,
            session_token_hash=self.hash_session_token(session_token),
            expires_at=datetime.now(UTC)
            + timedelta(seconds=self.settings.AUTH_SESSION_TTL_SECONDS),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.repository.session.commit()
        return session_token, auth_session

    async def resolve_user_from_session_token(self, session_token: str) -> User | None:
        auth_session = await self.repository.get_active_session_by_token_hash(
            self.hash_session_token(session_token)
        )
        if auth_session is None:
            return None
        return await self.repository.get_user_by_id(auth_session.user_id)

    async def revoke_session_token(self, session_token: str) -> bool:
        auth_session = await self.repository.get_active_session_by_token_hash(
            self.hash_session_token(session_token)
        )
        if auth_session is None:
            return False
        await self.repository.revoke_session(auth_session)
        await self.repository.session.commit()
        return True

    async def verify_otp(
        self,
        *,
        challenge_id: uuid.UUID,
        otp_code: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> OtpVerificationResult:
        challenge = await self.repository.get_otp_challenge_by_id_for_update(challenge_id)
        if challenge is None:
            raise OtpChallengeNotFoundError()

        self._ensure_challenge_is_verifiable(challenge)

        provided_hash = self.hash_otp_code(otp_code)
        if not hmac.compare_digest(challenge.otp_code_hash, provided_hash):
            await self.repository.increment_otp_challenge_attempt_count(challenge)
            await self.repository.session.commit()
            if challenge.attempt_count >= challenge.max_attempts:
                raise OtpAttemptLimitExceededError()
            raise OtpInvalidError()

        user = await self.get_or_create_user(email=challenge.email)
        authenticated_at = datetime.now(UTC)
        await self.repository.consume_otp_challenge(challenge)
        session_token, auth_session = await self.create_session_for_user(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return OtpVerificationResult(
            user=user,
            authenticated_at=authenticated_at,
            session_token=session_token,
            session=auth_session,
        )

    def hash_otp_code(self, otp_code: str) -> str:
        return self._hmac_hex(self.settings.AUTH_OTP_HASH_SECRET, otp_code)

    def hash_session_token(self, session_token: str) -> str:
        return self._hmac_hex(self.settings.AUTH_SESSION_HASH_SECRET, session_token)

    def _generate_numeric_otp(self) -> str:
        upper_bound = 10**self.settings.AUTH_OTP_CODE_LENGTH
        otp_value = secrets.randbelow(upper_bound)
        return str(otp_value).zfill(self.settings.AUTH_OTP_CODE_LENGTH)

    @staticmethod
    def _ensure_challenge_is_verifiable(challenge: OtpChallenge) -> None:
        now = datetime.now(UTC)
        if challenge.consumed_at is not None:
            raise OtpChallengeConsumedError()
        if challenge.expires_at <= now:
            raise OtpExpiredError()
        if challenge.attempt_count >= challenge.max_attempts:
            raise OtpAttemptLimitExceededError()

    @staticmethod
    def _hmac_hex(secret_value: str, raw_value: str) -> str:
        return hmac.new(
            secret_value.encode("utf-8"),
            raw_value.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
