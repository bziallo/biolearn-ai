from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.authz import current_principal, users_exist
from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    InvitationAcceptRequest,
    LoginRequest,
    LoginResponse,
    UserSummary,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["system"])


class AuthStatus(BaseModel):
    required: bool
    authenticated: bool


def _user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("", response_model=AuthStatus, summary="Whether this server needs a login")
def auth_status(request: Request, db: Session = Depends(get_db)) -> AuthStatus:
    settings = get_settings()
    if not users_exist(db):
        if not settings.auth_required:
            return AuthStatus(required=False, authenticated=True)
        provided = auth_service.token_header(request.headers)
        expected = settings.access_token.get_secret_value().strip()  # type: ignore[union-attr]
        return AuthStatus(
            required=True,
            authenticated=bool(provided) and hmac.compare_digest(provided, expected),
        )
    provided = auth_service.token_header(request.headers)
    authenticated = bool(provided) and auth_service.resolve_session(db, provided) is not None
    return AuthStatus(required=True, authenticated=authenticated)


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    user, token = auth_service.login(
        db,
        username=payload.username,
        password=payload.password,
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return LoginResponse(token=token, user=_user_summary(user))


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    token = auth_service.token_header(request.headers)
    auth_service.revoke_session(db, token)
    return {"ok": True}


@router.get("/me", response_model=UserSummary)
def me(db: Session = Depends(get_db)) -> UserSummary:
    principal = current_principal()
    if principal.user_id is None:
        raise DomainError(401, "auth_required", "需要登录")
    user = db.get(User, principal.user_id)
    if user is None:
        raise DomainError(401, "auth_required", "需要登录")
    return _user_summary(user)


@router.post("/invitations/accept", response_model=LoginResponse)
def accept_invitation(
    payload: InvitationAcceptRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    user, token = auth_service.accept_invitation(
        db,
        token=payload.token,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return LoginResponse(token=token, user=_user_summary(user))
