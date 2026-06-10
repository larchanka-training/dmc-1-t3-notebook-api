from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, field_validator


class RequestOtpRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Email must not be empty.")
        if normalized.count("@") != 1:
            raise ValueError("Email must be valid.")
        local_part, domain_part = normalized.split("@", maxsplit=1)
        if not local_part or not domain_part or "." not in domain_part:
            raise ValueError("Email must be valid.")
        if any(ch.isspace() for ch in normalized):
            raise ValueError("Email must be valid.")
        return normalized


class RequestOtpResponse(BaseModel):
    challenge_id: str
    expires_in_seconds: int
    dev_otp: str | None = None


class VerifyOtpRequest(BaseModel):
    challenge_id: uuid.UUID
    otp_code: str

    @field_validator("otp_code")
    @classmethod
    def validate_otp_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isdigit() or len(normalized) != 6:
            raise ValueError("OTP code must be a 6-digit numeric string.")
        return normalized


class VerifyOtpResponse(BaseModel):
    user: "UserSummary"
    authenticated_at: str


class SessionResponse(BaseModel):
    authenticated: bool
    user: "UserSummary | None"


class LogoutResponse(BaseModel):
    logged_out: bool


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str | None

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return str(value)


class ErrorDetails(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetails
