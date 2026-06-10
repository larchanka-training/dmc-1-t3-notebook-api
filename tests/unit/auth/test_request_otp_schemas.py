from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.features.auth.schemas import RequestOtpRequest


def test_request_otp_schema_normalizes_email() -> None:
    payload = RequestOtpRequest(email="  Test.User@Example.com  ")

    assert payload.email == "test.user@example.com"


def test_request_otp_schema_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        RequestOtpRequest(email="not-an-email")
