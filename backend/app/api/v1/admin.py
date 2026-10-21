from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.authz import current_principal, ensure_owner
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    GrantCreateRequest,
    GrantRead,
    InvitationCreateRequest,
    InvitationRead,
    UserStatusRequest,
    UserSummary,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _owner(db: Session) -> User:
    principal = ensure_owner()
    user = db.get(User, principal.user_id) if principal.user_id else None
    if user is None:
        from app.core.errors import DomainError

        raise DomainError(401, "auth_required", "需要登录")
    return user


def _summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("/users", response_model=list[UserSummary])
def list_users(db: Session = Depends(get_db)) -> list[UserSummary]:
    ensure_owner()
    return [_summary(user) for user in auth_service.list_users(db)]


@router.patch("/users/{user_id}", response_model=UserSummary)
def update_user(
    user_id: str,
    payload: UserStatusRequest,
    db: Session = Depends(get_db),
) -> UserSummary:
    owner = _owner(db)
    user = auth_service.set_user_status(db, user_id, payload.status)
    if user.id == owner.id and payload.status != "active":
        from app.core.errors import DomainError

        raise DomainError(409, "owner_cannot_be_disabled", "不能停用所有者")
    return _summary(user)


@router.get("/invitations", response_model=list[InvitationRead])
def list_invitations(db: Session = Depends(get_db)) -> list[InvitationRead]:
    ensure_owner()
    return [
        InvitationRead(
            id=item.id,
            note=item.note,
            role=item.role,
            created_at=item.created_at,
            expires_at=item.expires_at,
            used_at=item.used_at,
            revoked_at=item.revoked_at,
        )
        for item in auth_service.list_invitations(db)
    ]


@router.post("/invitations", response_model=InvitationRead)
def create_invitation(
    payload: InvitationCreateRequest,
    db: Session = Depends(get_db),
) -> InvitationRead:
    owner = _owner(db)
    invitation, token = auth_service.create_invitation(
        db, owner=owner, note=payload.note
    )
    return InvitationRead(
        id=invitation.id,
        note=invitation.note,
        role=invitation.role,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        used_at=invitation.used_at,
        revoked_at=invitation.revoked_at,
        invitation_token=token,
    )


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
) -> Response:
    owner = _owner(db)
    auth_service.revoke_invitation(db, owner=owner, invitation_id=invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/grants", response_model=list[GrantRead])
def list_grants(db: Session = Depends(get_db)) -> list[GrantRead]:
    ensure_owner()
    return [
        GrantRead(
            id=item.id,
            subject_id=item.subject_id,
            grantee_user_id=item.grantee_user_id,
            permission=item.permission,
            created_at=item.created_at,
        )
        for item in auth_service.list_grants(db)
    ]


@router.post("/grants", response_model=GrantRead)
def create_grant(
    payload: GrantCreateRequest,
    db: Session = Depends(get_db),
) -> GrantRead:
    owner = _owner(db)
    grant = auth_service.grant_subject(
        db,
        owner=owner,
        subject_id=payload.subject_id,
        grantee_user_id=payload.grantee_user_id,
        permission=payload.permission,
    )
    return GrantRead(
        id=grant.id,
        subject_id=grant.subject_id,
        grantee_user_id=grant.grantee_user_id,
        permission=grant.permission,
        created_at=grant.created_at,
    )


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_grant(grant_id: str, db: Session = Depends(get_db)) -> Response:
    owner = _owner(db)
    auth_service.revoke_grant(db, owner=owner, grant_id=grant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
