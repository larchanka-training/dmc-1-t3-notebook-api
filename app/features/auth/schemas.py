from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RequestOtpBody(BaseModel):
    email: EmailStr


class RequestOtpResponse(BaseModel):
    challenge_id: str
    expires_in_seconds: int
    dev_otp: str | None = None


class VerifyOtpBody(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=64)
    otp_code: str = Field(min_length=6, max_length=6)

    @field_validator("otp_code")
    @classmethod
    def validate_otp_code(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("otp_code must be a 6-digit numeric code")
        return value


class UserSummary(BaseModel):
    id: UUID
    email: str
    display_name: str | None = None


class VerifyOtpResponse(BaseModel):
    user: UserSummary
    authenticated_at: datetime


class SessionResponse(BaseModel):
    authenticated: bool
    user: UserSummary | None = None


class LogoutResponse(BaseModel):
    logged_out: bool = True
