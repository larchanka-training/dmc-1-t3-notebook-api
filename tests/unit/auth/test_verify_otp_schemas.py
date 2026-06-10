from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.features.auth.schemas import VerifyOtpRequest


def test_verify_otp_schema_accepts_uuid_and_numeric_code() -> None:
    payload = VerifyOtpRequest(
        challenge_id=uuid.uuid4(),
        otp_code="123456",
    )

    assert payload.otp_code == "123456"


@pytest.mark.parametrize("otp_code", ["", "12345", "1234567", "12a456", " 12345 "])
def test_verify_otp_schema_rejects_invalid_code(otp_code: str) -> None:
    with pytest.raises(ValidationError):
        VerifyOtpRequest(
            challenge_id=uuid.uuid4(),
            otp_code=otp_code,
        )
