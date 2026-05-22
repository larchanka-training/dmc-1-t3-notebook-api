from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.features.auth.dependencies import get_auth_service, get_client_ip
from app.features.auth.schemas import (
    LogoutResponse,
    RequestOtpBody,
    RequestOtpResponse,
    SessionResponse,
    VerifyOtpBody,
    VerifyOtpResponse,
)
from app.features.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-otp", response_model=RequestOtpResponse)
def request_otp(
    body: RequestOtpBody,
    background_tasks: BackgroundTasks,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> RequestOtpResponse:
    return auth_service.request_otp(
        email=str(body.email),
        client_ip=client_ip,
        background_tasks=background_tasks,
    )


@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp(
    body: VerifyOtpBody,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> VerifyOtpResponse:
    return auth_service.verify_otp(
        challenge_id=body.challenge_id,
        otp_code=body.otp_code,
        response=response,
        client_ip=client_ip,
    )


@router.get("/session", response_model=SessionResponse)
def get_session(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> SessionResponse:
    return auth_service.get_session(request=request)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LogoutResponse:
    return auth_service.logout(request=request, response=response)


@router.get("/google/start")
def google_start(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> RedirectResponse:
    authorization_url = auth_service.google_start()
    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/google/callback")
def google_callback(
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    redirect_url = auth_service.google_callback(
        code=code,
        state=state,
        error=error,
        response=response,
    )
    return RedirectResponse(url=redirect_url, status_code=302)
