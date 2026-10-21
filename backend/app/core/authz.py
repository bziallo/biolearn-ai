from __future__ import annotations

from dataclasses import dataclass
from contextvars import ContextVar, Token

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import PracticeSession, Subject, SubjectGrant, User


@dataclass(frozen=True)
class Principal:
    """Request identity.

    ``legacy`` is used only before the first account exists (and by direct
    service tests). It keeps the old single-user behaviour but is never
    produced once a user row exists.
    """

    user_id: str | None
    username: str
    role: str
    legacy: bool = False

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def can_write(self) -> bool:
        return self.legacy or self.is_owner


LEGACY_PRINCIPAL = Principal(None, "legacy", "owner", True)
_current: ContextVar[Principal | None] = ContextVar("biolearn_principal", default=None)


def current_principal() -> Principal:
    # Direct service calls (unit tests, maintenance scripts) retain full access.
    # Every HTTP request goes through AuthenticationMiddleware, which sets this.
    return _current.get() or LEGACY_PRINCIPAL


def set_current_principal(principal: Principal) -> Token:
    return _current.set(principal)


def reset_current_principal(token: Token) -> None:
    _current.reset(token)


def users_exist(db: Session) -> bool:
    return db.scalar(select(User.id).limit(1)) is not None


def ensure_owner(principal: Principal | None = None) -> Principal:
    active = principal or current_principal()
    if not active.can_write:
        raise DomainError(403, "owner_required", "只有所有者可以执行该操作")
    return active


def accessible_subject_ids(db: Session, principal: Principal | None = None) -> set[str] | None:
    """Return None for full access, or the set of granted subject ids."""

    active = principal or current_principal()
    if active.can_write:
        return None
    rows = db.scalars(
        select(SubjectGrant.subject_id).where(
            SubjectGrant.grantee_user_id == active.user_id,
            SubjectGrant.revoked_at.is_(None),
        )
    ).all()
    return set(rows)


def ensure_subject_access(
    db: Session,
    subject_id: str,
    *,
    write: bool = False,
    principal: Principal | None = None,
) -> Subject:
    active = principal or current_principal()
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise DomainError(404, "subject_not_found", "学科不存在")
    if active.legacy or active.is_owner:
        return subject
    if write:
        raise DomainError(403, "subject_forbidden", "没有该学科的写入权限")
    grant = db.scalar(
        select(SubjectGrant.id).where(
            SubjectGrant.subject_id == subject_id,
            SubjectGrant.grantee_user_id == active.user_id,
            SubjectGrant.revoked_at.is_(None),
        )
    )
    if grant is None:
        # Do not reveal whether the subject exists to an unauthorised user.
        raise DomainError(404, "subject_not_found", "学科不存在")
    return subject


def ensure_practice_session_access(
    db: Session,
    session: PracticeSession,
    *,
    principal: Principal | None = None,
) -> PracticeSession:
    active = principal or current_principal()
    if active.legacy:
        return session
    if session.user_id is None or session.user_id != active.user_id:
        raise DomainError(404, "practice_session_not_found", "练习记录不存在")
    return session


def principal_from_user(user: User) -> Principal:
    return Principal(user.id, user.username, user.role, False)
