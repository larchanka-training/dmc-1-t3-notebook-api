import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta


def normalize_email(email: str) -> str:
    return email.strip().lower()


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_value(value: str, *, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_hash(value: str, stored_hash: str, *, secret: str) -> bool:
    return hmac.compare_digest(hash_value(value, secret=secret), stored_hash)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def add_seconds(dt: datetime, seconds: int) -> datetime:
    base = as_utc_aware(dt)
    return base + timedelta(seconds=seconds)
