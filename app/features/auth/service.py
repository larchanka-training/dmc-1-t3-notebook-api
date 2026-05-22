import logging
import secrets
import uuid
from datetime import datetime

from fastapi import BackgroundTasks, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    add_seconds,
    as_utc_aware,
    generate_otp_code,
    generate_session_token,
    hash_value,
    normalize_email,
    utc_now,
    verify_hash,
)
from app.features.auth.cookies import clear_session_cookie, set_session_cookie
from app.features.auth.models import AuthSession, OAuthAccount, OAuthState, OtpChallenge, User
from app.features.auth.rate_limit import otp_request_limiter, otp_verify_limiter
from app.features.auth.repository import AuthRepository
from app.features.auth.schemas import (
    LogoutResponse,
    RequestOtpResponse,
    SessionResponse,
    UserSummary,
    VerifyOtpResponse,
)
from app.integrations.email.service import send_otp_email
from app.integrations.google_oauth.client import GoogleOAuthClient

logger = logging.getLogger(__name__)


def _new_challenge_id() -> str:
    return f"otp_ch_{uuid.uuid4().hex}"


def user_to_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
    )


def _google_email_verified(profile: dict) -> bool:
    value = profile.get("email_verified")
    return value is True or value == "true"


class AuthService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = AuthRepository(db)

    def request_otp(
        self,
        *,
        email: str,
        client_ip: str | None,
        background_tasks: BackgroundTasks,
    ) -> RequestOtpResponse:
        if not self.settings.otp_delivery_available:
            raise AppError(
                code="otp_delivery_unavailable",
                message="OTP delivery is not configured for this environment.",
                status_code=503,
            )

        normalized = normalize_email(email)
        now = utc_now()
        self._enforce_db_otp_request_rate_limit(email=normalized, now=now)
        self._enforce_rate_limit(
            limiter=otp_request_limiter,
            keys=[f"otp-request:ip:{client_ip or 'unknown'}"],
            limit=self.settings.OTP_REQUEST_RATE_LIMIT,
            window_seconds=self.settings.OTP_REQUEST_RATE_WINDOW_SECONDS,
            error_code="otp_request_rate_limited",
            message="Too many OTP requests. Try again later.",
        )

        existing = self.repo.get_active_otp_challenge_for_email(normalized)
        if existing is not None:
            self.repo.mark_otp_challenge_replaced(existing, now=now)

        otp_code = generate_otp_code()
        challenge = OtpChallenge(
            id=_new_challenge_id(),
            email=normalized,
            otp_hash=hash_value(otp_code, secret=self.settings.SESSION_SECRET_KEY),
            expires_at=add_seconds(now, self.settings.OTP_EXPIRES_SECONDS),
            attempt_count=0,
            max_attempts=self.settings.OTP_MAX_ATTEMPTS,
            created_at=now,
        )
        self.repo.create_otp_challenge(challenge)
        self.repo.commit()

        if self.settings.OTP_EMAIL_DELIVERY_ENABLED:
            background_tasks.add_task(send_otp_email, normalized, otp_code)

        logger.info(
            "OTP challenge created",
            extra={"email": normalized, "challenge_id": challenge.id},
        )

        return RequestOtpResponse(
            challenge_id=challenge.id,
            expires_in_seconds=self.settings.OTP_EXPIRES_SECONDS,
            dev_otp=otp_code if self.settings.expose_dev_otp else None,
        )

    def verify_otp(
        self,
        *,
        challenge_id: str,
        otp_code: str,
        response: Response,
        client_ip: str | None,
    ) -> VerifyOtpResponse:
        self._enforce_rate_limit(
            limiter=otp_verify_limiter,
            keys=[
                f"otp-verify:challenge:{challenge_id}",
                f"otp-verify:ip:{client_ip or 'unknown'}",
            ],
            limit=self.settings.OTP_VERIFY_RATE_LIMIT,
            window_seconds=self.settings.OTP_VERIFY_RATE_WINDOW_SECONDS,
            error_code="otp_attempt_limit_exceeded",
            message="Too many OTP verification attempts. Try again later.",
        )

        challenge = self.repo.get_otp_challenge_for_update(challenge_id)
        if challenge is None:
            raise AppError(
                code="otp_challenge_not_found",
                message="The OTP challenge was not found.",
                status_code=401,
            )

        now = utc_now()
        self._validate_otp_challenge_state(challenge, now=now)

        if not verify_hash(
            otp_code,
            challenge.otp_hash,
            secret=self.settings.SESSION_SECRET_KEY,
        ):
            self.repo.increment_otp_attempt(challenge)
            self.repo.commit()
            if challenge.attempt_count >= challenge.max_attempts:
                raise AppError(
                    code="otp_attempt_limit_exceeded",
                    message="OTP attempt limit exceeded.",
                    status_code=429,
                )
            raise AppError(
                code="otp_invalid",
                message="The provided OTP code is invalid.",
                status_code=401,
            )

        user = self.repo.get_user_by_email(challenge.email)
        if user is None:
            user = self.repo.create_user(email=challenge.email, now=now)

        self.repo.mark_otp_challenge_consumed(challenge, now=now)
        authenticated_at = self._establish_session(user=user, response=response, now=now)
        self.repo.commit()

        return VerifyOtpResponse(
            user=user_to_summary(user),
            authenticated_at=authenticated_at,
        )

    def get_session(self, *, request: Request) -> SessionResponse:
        user = self.resolve_user_from_request(request)
        if user is None:
            return SessionResponse(authenticated=False, user=None)
        return SessionResponse(authenticated=True, user=user_to_summary(user))

    def logout(self, *, request: Request, response: Response) -> LogoutResponse:
        token = request.cookies.get(self.settings.SESSION_COOKIE_NAME)
        if token:
            token_hash = hash_value(token, secret=self.settings.SESSION_SECRET_KEY)
            session = self.repo.get_session_by_token_hash(token_hash)
            if session is not None and session.revoked_at is None:
                self.repo.revoke_session(session, now=utc_now())
                self.repo.commit()

        clear_session_cookie(response, settings=self.settings)
        return LogoutResponse()

    def google_start(self) -> str:
        if not self.settings.google_oauth_enabled:
            raise AppError(
                code="google_oauth_not_configured",
                message="Google OAuth is not configured.",
                status_code=503,
            )

        now = utc_now()
        state = secrets.token_urlsafe(32)
        oauth_state = OAuthState(
            state=state,
            expires_at=add_seconds(now, 600),
            created_at=now,
        )
        self.repo.create_oauth_state(oauth_state)
        self.repo.commit()

        client = GoogleOAuthClient(self.settings)
        return client.build_authorization_url(state)

    def google_callback(
        self,
        *,
        code: str | None,
        state: str | None,
        error: str | None,
        response: Response,
    ) -> str:
        if error or not code or not state:
            return self._frontend_auth_error_redirect("oauth_failed")

        if not self.settings.google_oauth_enabled:
            return self._frontend_auth_error_redirect("google_oauth_not_configured")

        oauth_state = self.repo.get_oauth_state(state)
        now = utc_now()
        if (
            oauth_state is None
            or oauth_state.consumed_at is not None
            or as_utc_aware(oauth_state.expires_at) <= now
        ):
            return self._frontend_auth_error_redirect("oauth_state_invalid")

        self.repo.consume_oauth_state(oauth_state, now=now)

        client = GoogleOAuthClient(self.settings)
        try:
            token_payload = client.exchange_code(code)
            profile = client.fetch_user_info(token_payload["access_token"])
        except Exception:
            logger.exception("Google OAuth callback failed")
            self.repo.rollback()
            return self._frontend_auth_error_redirect("oauth_provider_error")

        if not _google_email_verified(profile):
            self.repo.rollback()
            return self._frontend_auth_error_redirect("oauth_email_unverified")

        provider_user_id = profile["sub"]
        email = normalize_email(profile.get("email", ""))
        if not email:
            self.repo.rollback()
            return self._frontend_auth_error_redirect("oauth_email_missing")

        account = self.repo.get_oauth_account(
            provider="google",
            provider_user_id=provider_user_id,
        )
        if account is not None:
            user = self.repo.get_user_by_id(account.user_id)
        else:
            user = self.repo.get_user_by_email(email)
            if user is None:
                user = self.repo.create_user(email=email, now=now)
            self.repo.create_oauth_account(
                OAuthAccount(
                    user_id=user.id,
                    provider="google",
                    provider_user_id=provider_user_id,
                    email=email,
                    created_at=now,
                )
            )

        if user is None:
            self.repo.rollback()
            return self._frontend_auth_error_redirect("oauth_user_resolution_failed")

        self._establish_session(user=user, response=response, now=now)
        self.repo.commit()
        return self.settings.FRONTEND_URL

    def resolve_user_from_request(self, request: Request) -> User | None:
        token = request.cookies.get(self.settings.SESSION_COOKIE_NAME)
        if not token:
            return None

        token_hash = hash_value(token, secret=self.settings.SESSION_SECRET_KEY)
        session = self.repo.get_session_by_token_hash(token_hash)
        if session is None:
            return None

        now = utc_now()
        if session.revoked_at is not None or as_utc_aware(session.expires_at) <= now:
            return None

        return self.repo.get_user_by_id(session.user_id)

    def _establish_session(
        self,
        *,
        user: User,
        response: Response,
        now: datetime,
    ) -> datetime:
        session_token = generate_session_token()
        session = AuthSession(
            user_id=user.id,
            token_hash=hash_value(session_token, secret=self.settings.SESSION_SECRET_KEY),
            created_at=now,
            expires_at=add_seconds(now, self.settings.SESSION_MAX_AGE_SECONDS),
        )
        self.repo.create_session(session)
        set_session_cookie(
            response,
            settings=self.settings,
            session_token=session_token,
            max_age_seconds=self.settings.SESSION_MAX_AGE_SECONDS,
        )
        return now

    def _validate_otp_challenge_state(self, challenge: OtpChallenge, *, now: datetime) -> None:
        if challenge.consumed_at is not None or challenge.replaced_at is not None:
            raise AppError(
                code="otp_challenge_not_found",
                message="The OTP challenge is no longer valid.",
                status_code=409,
            )
        if as_utc_aware(challenge.expires_at) <= now:
            raise AppError(
                code="otp_expired",
                message="The OTP challenge has expired.",
                status_code=401,
            )
        if challenge.attempt_count >= challenge.max_attempts:
            raise AppError(
                code="otp_attempt_limit_exceeded",
                message="OTP attempt limit exceeded.",
                status_code=429,
            )

    def _enforce_db_otp_request_rate_limit(self, *, email: str, now: datetime) -> None:
        window_seconds = self.settings.OTP_REQUEST_RATE_WINDOW_SECONDS
        since = add_seconds(now, -window_seconds)
        request_count = self.repo.count_otp_challenges_by_email_since(email, since=since)
        if request_count >= self.settings.OTP_REQUEST_RATE_LIMIT:
            raise AppError(
                code="otp_request_rate_limited",
                message="Too many OTP requests. Try again later.",
                status_code=429,
                retry_after_seconds=window_seconds,
            )

    def _enforce_rate_limit(
        self,
        *,
        limiter,
        keys: list[str],
        limit: int,
        window_seconds: int,
        error_code: str,
        message: str,
    ) -> None:
        for key in keys:
            result = limiter.check(key, limit=limit, window_seconds=window_seconds)
            if not result.allowed:
                raise AppError(
                    code=error_code,
                    message=message,
                    status_code=429,
                    retry_after_seconds=result.retry_after_seconds,
                )

    def _frontend_auth_error_redirect(self, code: str) -> str:
        base = self.settings.FRONTEND_URL.rstrip("/")
        return f"{base}/auth/error?code={code}"
