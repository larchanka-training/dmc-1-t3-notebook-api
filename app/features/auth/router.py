from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import Settings, get_settings
from app.features.auth.cookies import clear_auth_session_cookie, set_auth_session_cookie
from app.features.auth.dependencies import (
    get_auth_service,
    get_optional_current_user,
    get_session_cookie_value,
)
from app.features.auth.schemas import (
    LogoutResponse,
    RequestOtpRequest,
    RequestOtpResponse,
    SessionResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
    UserSummary,
)
from app.features.auth.service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/request-otp",
    response_model=RequestOtpResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Create an email OTP challenge",
)
async def request_otp(
    payload: RequestOtpRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> RequestOtpResponse:
    result = await auth_service.request_otp(email=payload.email)
    return RequestOtpResponse(
        challenge_id=result.challenge_id,
        expires_in_seconds=result.expires_in_seconds,
        dev_otp=result.dev_otp,
    )


@router.post(
    "/verify-otp",
    response_model=VerifyOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify an email OTP challenge",
)
async def verify_otp(
    payload: VerifyOtpRequest,
    response: Response,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> VerifyOtpResponse:
    result = await auth_service.verify_otp(
        challenge_id=payload.challenge_id,
        otp_code=payload.otp_code,
        ip_address=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    set_auth_session_cookie(response, result.session_token, settings)
    return VerifyOtpResponse(
        user=UserSummary.model_validate(result.user),
        authenticated_at=result.authenticated_at.isoformat().replace("+00:00", "Z"),
    )


@router.get(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the current authenticated session state",
)
async def get_session(
    current_user: UserSummary | None = Depends(get_optional_current_user),
) -> SessionResponse:
    return SessionResponse(
        authenticated=current_user is not None,
        user=current_user,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Invalidate the current authenticated session",
)
async def logout(
    response: Response,
    session_token: str | None = Depends(get_session_cookie_value),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> LogoutResponse:
    if session_token is not None:
        await auth_service.revoke_session_token(session_token)

    clear_auth_session_cookie(response, settings)
    return LogoutResponse(logged_out=True)
