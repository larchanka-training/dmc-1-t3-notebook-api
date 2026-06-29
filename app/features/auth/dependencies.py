from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.features.auth.cookies import read_auth_session_cookie
from app.features.auth.repository import AuthRepository
from app.features.auth.service import AuthService
from app.features.auth.schemas import UserSummary
from app.integrations.email_delivery import (
    LoggingOtpDeliveryGateway,
    OtpDeliveryGateway,
    SesOtpDeliveryGateway,
)
from app.integrations.google_oauth.client import GoogleOAuthClient


def get_auth_repository(db: AsyncSession = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)


def get_otp_delivery_gateway(
    settings: Settings = Depends(get_settings),
) -> OtpDeliveryGateway:
    if settings.auth_dev_otp_enabled:
        return LoggingOtpDeliveryGateway()
    if settings.ses_email_enabled:
        return SesOtpDeliveryGateway(
            from_email=settings.SES_FROM_EMAIL,
            region=settings.SES_REGION,
        )
    return LoggingOtpDeliveryGateway()


def get_google_oauth_client(
    settings: Settings = Depends(get_settings),
) -> GoogleOAuthClient:
    return GoogleOAuthClient(settings)


def get_auth_service(
    repository: AuthRepository = Depends(get_auth_repository),
    settings: Settings = Depends(get_settings),
    otp_delivery_gateway: OtpDeliveryGateway = Depends(get_otp_delivery_gateway),
    google_oauth_client: GoogleOAuthClient = Depends(get_google_oauth_client),
) -> AuthService:
    return AuthService(
        repository=repository,
        settings=settings,
        otp_delivery_gateway=otp_delivery_gateway,
        google_oauth_client=google_oauth_client,
    )


def get_session_cookie_value(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> str | None:
    return read_auth_session_cookie(request, settings)


async def get_optional_current_user(
    session_token: str | None = Depends(get_session_cookie_value),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserSummary | None:
    if session_token is None:
        return None

    user = await auth_service.resolve_user_from_session_token(session_token)
    if user is None:
        return None

    return UserSummary(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
    )


async def get_current_user(
    user: UserSummary | None = Depends(get_optional_current_user),
) -> UserSummary:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user
