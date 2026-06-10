from __future__ import annotations


class AuthError(Exception):
    """Base auth exception converted to a stable API error response."""

    status_code = 400
    code = "auth_error"
    message = "Authentication request failed."

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class AuthRateLimitError(AuthError):
    status_code = 429
    code = "otp_request_rate_limited"
    message = "Too many OTP requests. Try again later."


class OtpInvalidError(AuthError):
    status_code = 401
    code = "otp_invalid"
    message = "The provided OTP code is invalid."


class OtpExpiredError(AuthError):
    status_code = 401
    code = "otp_expired"
    message = "The OTP challenge has expired."


class OtpChallengeNotFoundError(AuthError):
    status_code = 401
    code = "otp_challenge_not_found"
    message = "The OTP challenge was not found."


class OtpAttemptLimitExceededError(AuthError):
    status_code = 429
    code = "otp_attempt_limit_exceeded"
    message = "Too many OTP attempts. Request a new code and try again."


class OtpChallengeConsumedError(AuthError):
    status_code = 409
    code = "otp_challenge_consumed"
    message = "The OTP challenge has already been used."
