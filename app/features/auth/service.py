from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.features.auth.errors import (
    AuthRateLimitError,
    GoogleOAuthNotConfiguredError,
    OtpAttemptLimitExceededError,
    OtpChallengeConsumedError,
    OtpChallengeNotFoundError,
    OtpExpiredError,
    OtpInvalidError,
)
from app.features.auth.models import OAuthState, OtpChallenge, Session, User
from app.features.auth.repository import AuthRepository
from app.integrations.email_delivery import OtpDeliveryGateway, OtpDeliveryMessage
from app.integrations.google_oauth.client import GoogleOAuthClient, GoogleOAuthIdentity


GOOGLE_OAUTH_PROVIDER = "google"
GOOGLE_OAUTH_FLOW = "google_oauth"


@dataclass(slots=True)
class GoogleOAuthStartResult:
    authorization_url: str
    state: str
    nonce: str


@dataclass(slots=True)
class GoogleOAuthCallbackSuccess:
    session_token: str
    redirect_url: str
    user: User


@dataclass(slots=True)
class GoogleOAuthCallbackError:
    code: str
    redirect_url: str


GoogleOAuthCallbackResult = GoogleOAuthCallbackSuccess | GoogleOAuthCallbackError


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
        google_oauth_client: GoogleOAuthClient,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.otp_delivery_gateway = otp_delivery_gateway
        self.google_oauth_client = google_oauth_client

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

    async def start_google_oauth(self) -> GoogleOAuthStartResult:
        self._ensure_google_oauth_configured()

        nonce = secrets.token_urlsafe(24)
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(seconds=self.settings.AUTH_OAUTH_STATE_TTL_SECONDS)
        state = self._sign_oauth_state(
            nonce=nonce,
            issued_at=issued_at,
            flow=GOOGLE_OAUTH_FLOW,
        )
        await self.repository.create_oauth_state(
            nonce=nonce,
            flow=GOOGLE_OAUTH_FLOW,
            expires_at=expires_at,
        )
        await self.repository.session.commit()

        return GoogleOAuthStartResult(
            authorization_url=self.google_oauth_client.build_authorization_url(state),
            state=state,
            nonce=nonce,
        )

    async def handle_google_callback(
        self,
        *,
        state: str | None,
        state_cookie_nonce: str | None,
        code: str | None,
        provider_error: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GoogleOAuthCallbackResult:
        validated_state = await self._validate_google_oauth_state(
            state=state,
            state_cookie_nonce=state_cookie_nonce,
        )
        if isinstance(validated_state, GoogleOAuthCallbackError):
            return validated_state

        if provider_error is not None:
            error_code = (
                "oauth_access_denied"
                if provider_error == "access_denied"
                else "oauth_provider_error"
            )
            return self._google_oauth_error_result(error_code)

        if not code:
            return self._google_oauth_error_result("oauth_exchange_failed")

        try:
            token_response = await self.google_oauth_client.exchange_code(code)
            access_token = token_response.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                return self._google_oauth_error_result("oauth_exchange_failed")

            identity = await self.google_oauth_client.fetch_user_info(access_token)
        except Exception:
            return self._google_oauth_error_result("oauth_exchange_failed")

        user = await self._resolve_user_for_google_identity(identity)
        if isinstance(user, GoogleOAuthCallbackError):
            return user

        session_token, _session = await self.create_session_for_user(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return GoogleOAuthCallbackSuccess(
            session_token=session_token,
            redirect_url=self.settings.GOOGLE_OAUTH_SUCCESS_REDIRECT_URL,
            user=user,
        )

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

    async def _validate_google_oauth_state(
        self,
        *,
        state: str | None,
        state_cookie_nonce: str | None,
    ) -> OAuthState | GoogleOAuthCallbackError:
        if state is None or state_cookie_nonce is None:
            return self._google_oauth_error_result("oauth_state_missing")

        try:
            payload = self._parse_signed_oauth_state(state)
        except ValueError:
            return self._google_oauth_error_result("oauth_state_invalid")

        if payload["flow"] != GOOGLE_OAUTH_FLOW:
            return self._google_oauth_error_result("oauth_state_invalid")

        issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
        now = datetime.now(UTC)
        if issued_at + timedelta(seconds=self.settings.AUTH_OAUTH_STATE_TTL_SECONDS) <= now:
            return self._google_oauth_error_result("oauth_state_expired")

        if payload["nonce"] != state_cookie_nonce:
            return self._google_oauth_error_result("oauth_state_invalid")

        oauth_state = await self.repository.get_oauth_state_by_nonce_for_update(payload["nonce"])
        if oauth_state is None or oauth_state.consumed_at is not None:
            return self._google_oauth_error_result("oauth_state_invalid")
        if oauth_state.expires_at <= now:
            return self._google_oauth_error_result("oauth_state_expired")

        await self.repository.consume_oauth_state(oauth_state)
        await self.repository.session.commit()
        return oauth_state

    async def _resolve_user_for_google_identity(
        self,
        identity: GoogleOAuthIdentity,
    ) -> User | GoogleOAuthCallbackError:
        if not identity.subject:
            return self._google_oauth_error_result("oauth_exchange_failed")

        existing_link = await self.repository.get_oauth_account_by_provider_subject(
            provider=GOOGLE_OAUTH_PROVIDER,
            provider_subject=identity.subject,
        )
        if existing_link is not None:
            user = await self.repository.get_user_by_id(existing_link.user_id)
            if user is None:
                return self._google_oauth_error_result("oauth_account_conflict")
            return user

        if not identity.email_verified or not identity.email:
            return self._google_oauth_error_result("oauth_identity_unverified")

        normalized_email = identity.email.strip().lower()
        if not normalized_email:
            return self._google_oauth_error_result("oauth_identity_unverified")

        user = await self.repository.get_user_by_email(normalized_email)
        try:
            if user is None:
                user = await self.repository.create_user(
                    email=normalized_email,
                    display_name=identity.display_name,
                )
            await self.repository.create_oauth_account(
                user_id=user.id,
                provider=GOOGLE_OAUTH_PROVIDER,
                provider_subject=identity.subject,
                provider_email=normalized_email,
            )
            await self.repository.session.commit()
        except IntegrityError:
            await self.repository.session.rollback()
            return self._google_oauth_error_result("oauth_account_conflict")

        return user

    def _ensure_google_oauth_configured(self) -> None:
        if not self.settings.google_oauth_enabled:
            raise GoogleOAuthNotConfiguredError()

    def _google_oauth_error_result(self, code: str) -> GoogleOAuthCallbackError:
        query = urlencode({"code": code})
        return GoogleOAuthCallbackError(
            code=code,
            redirect_url=f"{self.settings.GOOGLE_OAUTH_ERROR_REDIRECT_URL}?{query}",
        )

    def _sign_oauth_state(
        self,
        *,
        nonce: str,
        issued_at: datetime,
        flow: str,
    ) -> str:
        payload = {
            "nonce": nonce,
            "iat": int(issued_at.timestamp()),
            "flow": flow,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        payload_b64 = self._urlsafe_b64encode(payload_bytes)
        signature = self._hmac_hex(self.settings.AUTH_OAUTH_STATE_SIGNING_SECRET, payload_b64)
        return f"{payload_b64}.{signature}"

    def _parse_signed_oauth_state(self, signed_state: str) -> dict[str, str | int]:
        try:
            payload_b64, signature = signed_state.split(".", maxsplit=1)
        except ValueError as exc:
            raise ValueError("Signed state is malformed.") from exc

        expected_signature = self._hmac_hex(
            self.settings.AUTH_OAUTH_STATE_SIGNING_SECRET,
            payload_b64,
        )
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Signed state signature is invalid.")

        try:
            payload_raw = urlsafe_b64decode(self._restore_padding(payload_b64)).decode("utf-8")
            payload = json.loads(payload_raw)
        except Exception as exc:
            raise ValueError("Signed state payload is invalid.") from exc

        nonce = payload.get("nonce")
        issued_at = payload.get("iat")
        flow = payload.get("flow")
        if not isinstance(nonce, str) or not isinstance(issued_at, int) or not isinstance(flow, str):
            raise ValueError("Signed state payload shape is invalid.")
        return {"nonce": nonce, "iat": issued_at, "flow": flow}

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

    @staticmethod
    def _urlsafe_b64encode(raw_bytes: bytes) -> str:
        return urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")

    @staticmethod
    def _restore_padding(value: str) -> str:
        return value + "=" * (-len(value) % 4)
