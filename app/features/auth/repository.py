import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.auth.models import AuthSession, OAuthAccount, OAuthState, OtpChallenge, User


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def create_user(self, *, email: str, now: datetime) -> User:
        user = User(email=email, created_at=now, updated_at=now)
        self.db.add(user)
        self.db.flush()
        return user

    def get_otp_challenge(self, challenge_id: str) -> OtpChallenge | None:
        return self.db.get(OtpChallenge, challenge_id)

    def get_otp_challenge_for_update(self, challenge_id: str) -> OtpChallenge | None:
        stmt = (
            select(OtpChallenge)
            .where(OtpChallenge.id == challenge_id)
            .with_for_update()
        )
        return self.db.scalar(stmt)

    def count_otp_challenges_by_email_since(self, email: str, *, since: datetime) -> int:
        count = self.db.scalar(
            select(func.count())
            .select_from(OtpChallenge)
            .where(
                OtpChallenge.email == email,
                OtpChallenge.created_at >= since,
            )
        )
        return int(count or 0)

    def get_active_otp_challenge_for_email(self, email: str) -> OtpChallenge | None:
        stmt = (
            select(OtpChallenge)
            .where(
                OtpChallenge.email == email,
                OtpChallenge.consumed_at.is_(None),
                OtpChallenge.replaced_at.is_(None),
            )
            .order_by(OtpChallenge.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def create_otp_challenge(self, challenge: OtpChallenge) -> OtpChallenge:
        self.db.add(challenge)
        self.db.flush()
        return challenge

    def mark_otp_challenge_replaced(self, challenge: OtpChallenge, *, now: datetime) -> None:
        challenge.replaced_at = now

    def mark_otp_challenge_consumed(self, challenge: OtpChallenge, *, now: datetime) -> None:
        challenge.consumed_at = now

    def increment_otp_attempt(self, challenge: OtpChallenge) -> None:
        challenge.attempt_count += 1
        self.db.flush()

    def create_session(self, session: AuthSession) -> AuthSession:
        self.db.add(session)
        self.db.flush()
        return session

    def get_session_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return self.db.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        )

    def revoke_session(self, session: AuthSession, *, now: datetime) -> None:
        session.revoked_at = now

    def create_oauth_state(self, oauth_state: OAuthState) -> OAuthState:
        self.db.add(oauth_state)
        self.db.flush()
        return oauth_state

    def get_oauth_state(self, state: str) -> OAuthState | None:
        return self.db.get(OAuthState, state)

    def consume_oauth_state(self, oauth_state: OAuthState, *, now: datetime) -> None:
        oauth_state.consumed_at = now

    def get_oauth_account(
        self, *, provider: str, provider_user_id: str
    ) -> OAuthAccount | None:
        return self.db.scalar(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )

    def create_oauth_account(self, account: OAuthAccount) -> OAuthAccount:
        self.db.add(account)
        self.db.flush()
        return account

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
