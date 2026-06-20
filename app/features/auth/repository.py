from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import OAuthAccount, OAuthState, OtpChallenge, Session, User


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return await self.session.scalar(stmt)

    async def create_user(
        self,
        *,
        email: str,
        display_name: str | None = None,
    ) -> User:
        user = User(email=email, display_name=display_name)
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_oauth_account_by_provider_subject(
        self,
        *,
        provider: str,
        provider_subject: str,
    ) -> OAuthAccount | None:
        stmt = (
            select(OAuthAccount)
            .where(OAuthAccount.provider == provider)
            .where(OAuthAccount.provider_subject == provider_subject)
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def create_oauth_account(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        provider_subject: str,
        provider_email: str | None,
    ) -> OAuthAccount:
        oauth_account = OAuthAccount(
            user_id=user_id,
            provider=provider,
            provider_subject=provider_subject,
            provider_email=provider_email,
        )
        self.session.add(oauth_account)
        await self.session.flush()
        return oauth_account

    async def create_oauth_state(
        self,
        *,
        nonce: str,
        flow: str,
        expires_at: datetime,
    ) -> OAuthState:
        oauth_state = OAuthState(
            nonce=nonce,
            flow=flow,
            expires_at=expires_at,
        )
        self.session.add(oauth_state)
        await self.session.flush()
        return oauth_state

    async def get_oauth_state_by_nonce_for_update(self, nonce: str) -> OAuthState | None:
        stmt = (
            select(OAuthState)
            .where(OAuthState.nonce == nonce)
            .with_for_update()
        )
        return await self.session.scalar(stmt)

    async def consume_oauth_state(self, oauth_state: OAuthState) -> OAuthState:
        oauth_state.consumed_at = datetime.now(UTC)
        await self.session.flush()
        return oauth_state

    async def get_recent_active_challenge_for_email(
        self,
        *,
        email: str,
        cooldown_seconds: int,
    ) -> OtpChallenge | None:
        now = datetime.now(UTC)
        stmt = (
            select(OtpChallenge)
            .where(OtpChallenge.email == email)
            .where(OtpChallenge.consumed_at.is_(None))
            .where(OtpChallenge.expires_at > now)
            .where(OtpChallenge.created_at >= now - timedelta(seconds=cooldown_seconds))
            .order_by(OtpChallenge.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def create_otp_challenge(
        self,
        *,
        email: str,
        otp_code_hash: str,
        expires_at: datetime,
        max_attempts: int,
    ) -> OtpChallenge:
        challenge = OtpChallenge(
            email=email,
            otp_code_hash=otp_code_hash,
            expires_at=expires_at,
            max_attempts=max_attempts,
        )
        self.session.add(challenge)
        await self.session.flush()
        return challenge

    async def get_otp_challenge_by_id(self, challenge_id: uuid.UUID) -> OtpChallenge | None:
        return await self.session.get(OtpChallenge, challenge_id)

    async def get_otp_challenge_by_id_for_update(
        self, challenge_id: uuid.UUID
    ) -> OtpChallenge | None:
        stmt = (
            select(OtpChallenge)
            .where(OtpChallenge.id == challenge_id)
            .with_for_update()
        )
        return await self.session.scalar(stmt)

    async def increment_otp_challenge_attempt_count(
        self, challenge: OtpChallenge
    ) -> OtpChallenge:
        challenge.attempt_count += 1
        await self.session.flush()
        return challenge

    async def consume_otp_challenge(self, challenge: OtpChallenge) -> OtpChallenge:
        challenge.consumed_at = datetime.now(UTC)
        await self.session.flush()
        return challenge

    async def create_session(
        self,
        *,
        user_id: uuid.UUID,
        session_token_hash: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Session:
        auth_session = Session(
            user_id=user_id,
            session_token_hash=session_token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(auth_session)
        await self.session.flush()
        return auth_session

    async def get_active_session_by_token_hash(self, token_hash: str) -> Session | None:
        now = datetime.now(UTC)
        stmt = (
            select(Session)
            .where(Session.session_token_hash == token_hash)
            .where(Session.revoked_at.is_(None))
            .where(Session.expires_at > now)
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def revoke_session(self, auth_session: Session) -> Session:
        auth_session.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return auth_session
