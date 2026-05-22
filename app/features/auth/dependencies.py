from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.features.auth.models import User
from app.features.auth.service import AuthService


def get_auth_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(db, settings)


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return None


def get_optional_user(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User | None:
    return auth_service._resolve_user_from_request(request)


def require_authenticated_user(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> User:
    if user is None:
        raise AppError(
            code="unauthenticated",
            message="Authentication is required.",
            status_code=401,
        )
    return user
