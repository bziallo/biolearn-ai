from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import AuthSession, Invitation, Subject, SubjectGrant, User

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
_username_re = re.compile(r"^[a-zA-Z0-9_.-]{3,40}$")
_login_attempts: dict[str, list[datetime]] = {}
_login_lock = threading.Lock()


def _now() -> datetime:
    """Naive UTC timestamps, matching SQLite's storage for DateTime columns."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def validate_username(value: str) -> str:
    username = value.strip().lower()
    if not _username_re.fullmatch(username):
        raise DomainError(
            422,
            "invalid_username",
            "用户名需为 3–40 位字母、数字、下划线、点或短横线",
        )
    return username


def validate_password(value: str) -> None:
    if len(value) < 10:
        raise DomainError(422, "weak_password", "密码至少需要 10 个字符")
    if len(value) > 200:
        raise DomainError(422, "invalid_password", "密码过长")


def hash_password(value: str) -> str:
    validate_password(value)
    return _hasher.hash(value)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_owner(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str = "Owner",
) -> User:
    if db.scalar(select(User.id).limit(1)) is not None:
        raise DomainError(409, "owner_exists", "已经存在用户，不能再初始化 Owner")
    owner = User(
        username=validate_username(username),
        display_name=display_name.strip()[:120] or "Owner",
        password_hash=hash_password(password),
        role="owner",
        status="active",
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


def _client_key(ip: str, username: str) -> str:
    return f"{ip}:{username.strip().lower()}"


def _check_rate_limit(key: str) -> None:
    settings = get_settings()
    cutoff = _now() - timedelta(minutes=settings.login_window_minutes)
    with _login_lock:
        attempts = [item for item in _login_attempts.get(key, []) if item >= cutoff]
        if len(attempts) >= settings.login_max_attempts:
            raise DomainError(
                429,
                "login_rate_limited",
                "登录失败次数过多，请稍后再试",
            )
        _login_attempts[key] = attempts


def _record_failure(key: str) -> None:
    with _login_lock:
        _login_attempts.setdefault(key, []).append(_now())


def _clear_failures(key: str) -> None:
    with _login_lock:
        _login_attempts.pop(key, None)


def reset_login_attempts() -> None:
    with _login_lock:
        _login_attempts.clear()


def _issue_session(
    db: Session,
    user: User,
    *,
    ip: str,
    user_agent: str,
) -> str:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=_now() + timedelta(hours=settings.session_ttl_hours),
            last_seen_at=_now(),
            ip_hash=_hash_text(ip) if ip else None,
            user_agent_hash=_hash_text(user_agent)[:64] if user_agent else None,
        )
    )
    db.commit()
    return token


def login(
    db: Session,
    *,
    username: str,
    password: str,
    ip: str = "",
    user_agent: str = "",
) -> tuple[User, str]:
    normalized = username.strip().lower()
    key = _client_key(ip, normalized)
    _check_rate_limit(key)
    user = db.scalar(select(User).where(User.username == normalized))
    if user is None or not verify_password(user.password_hash, password):
        _record_failure(key)
        raise DomainError(401, "invalid_credentials", "用户名或密码错误")
    if user.status != "active":
        raise DomainError(403, "user_disabled", "账号已停用")
    _clear_failures(key)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = _now()
    token = _issue_session(db, user, ip=ip, user_agent=user_agent)
    db.commit()
    db.refresh(user)
    return user, token


def resolve_session(db: Session, token: str) -> User | None:
    if not token:
        return None
    now = _now()
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == _hash_token(token),
            AuthSession.revoked_at.is_(None),
        )
    )
    if session is None:
        return None
    settings = get_settings()
    if session.expires_at <= now:
        return None
    if session.last_seen_at + timedelta(hours=settings.session_idle_hours) <= now:
        return None
    user = db.get(User, session.user_id)
    if user is None or user.status != "active":
        return None
    # Avoid a write on every single request; five-minute resolution is enough
    # for idle expiry and keeps SQLite write pressure low.
    if session.last_seen_at + timedelta(minutes=5) <= now:
        session.last_seen_at = now
        db.commit()
    return user


def revoke_session(db: Session, token: str) -> None:
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == _hash_token(token),
            AuthSession.revoked_at.is_(None),
        )
    )
    if session is not None:
        session.revoked_at = _now()
        db.commit()


def revoke_all_sessions(db: Session, user_id: str) -> None:
    sessions = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
    ).all()
    for session in sessions:
        session.revoked_at = _now()
    db.commit()


def create_invitation(
    db: Session,
    *,
    owner: User,
    note: str = "",
    ttl_hours: int | None = None,
) -> tuple[Invitation, str]:
    if owner.role != "owner":
        raise DomainError(403, "owner_required", "只有所有者可以邀请用户")
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        token_hash=_hash_token(token),
        created_by=owner.id,
        role="user",
        note=(note or "").strip()[:500],
        expires_at=_now()
        + timedelta(hours=ttl_hours or settings.invite_ttl_hours),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation, token


def accept_invitation(
    db: Session,
    *,
    token: str,
    username: str,
    password: str,
    display_name: str = "",
    ip: str = "",
    user_agent: str = "",
) -> tuple[User, str]:
    now = _now()
    invitation = db.scalar(
        select(Invitation).where(
            Invitation.token_hash == _hash_token(token),
            Invitation.used_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
    )
    if invitation is None or invitation.expires_at <= now:
        raise DomainError(422, "invitation_invalid", "邀请链接无效或已过期")
    normalized = validate_username(username)
    if db.scalar(select(User.id).where(User.username == normalized)) is not None:
        raise DomainError(409, "username_taken", "用户名已被使用")
    user = User(
        username=normalized,
        display_name=(display_name or normalized)[:120],
        password_hash=hash_password(password),
        role="user",
        status="active",
    )
    db.add(user)
    db.flush()
    invitation.used_at = now
    invitation.used_by = user.id
    token_value = _issue_session(db, user, ip=ip, user_agent=user_agent)
    db.commit()
    db.refresh(user)
    return user, token_value


def revoke_invitation(db: Session, *, owner: User, invitation_id: str) -> None:
    if owner.role != "owner":
        raise DomainError(403, "owner_required", "只有所有者可以撤销邀请")
    invitation = db.get(Invitation, invitation_id)
    if invitation is None:
        raise DomainError(404, "invitation_not_found", "邀请不存在")
    invitation.revoked_at = _now()
    db.commit()


def list_invitations(db: Session) -> list[Invitation]:
    return list(db.scalars(select(Invitation).order_by(Invitation.created_at.desc())).all())


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)).all())


def set_user_status(db: Session, user_id: str, status: str) -> User:
    if status not in {"active", "disabled"}:
        raise DomainError(422, "invalid_status", "无效的用户状态")
    user = db.get(User, user_id)
    if user is None:
        raise DomainError(404, "user_not_found", "用户不存在")
    if user.role == "owner" and status == "disabled":
        raise DomainError(409, "owner_cannot_be_disabled", "不能停用所有者")
    user.status = status
    if status == "disabled":
        revoke_all_sessions(db, user.id)
    db.commit()
    db.refresh(user)
    return user


def grant_subject(
    db: Session,
    *,
    owner: User,
    subject_id: str,
    grantee_user_id: str,
    permission: str = "read",
) -> SubjectGrant:
    if owner.role != "owner":
        raise DomainError(403, "owner_required", "只有所有者可以授权")
    if permission not in {"read", "practice", "write"}:
        raise DomainError(422, "invalid_permission", "无效的共享权限")
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise DomainError(404, "subject_not_found", "学科不存在")
    grantee = db.get(User, grantee_user_id)
    if grantee is None or grantee.role == "owner":
        raise DomainError(422, "invalid_grantee", "只能授权给普通用户")
    existing = db.scalar(
        select(SubjectGrant).where(
            SubjectGrant.subject_id == subject_id,
            SubjectGrant.grantee_user_id == grantee_user_id,
            SubjectGrant.revoked_at.is_(None),
        )
    )
    if existing is not None:
        existing.permission = permission
        db.commit()
        db.refresh(existing)
        return existing
    grant = SubjectGrant(
        subject_id=subject_id,
        grantee_user_id=grantee_user_id,
        permission=permission,
        created_by=owner.id,
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    return grant


def revoke_grant(db: Session, *, owner: User, grant_id: str) -> None:
    if owner.role != "owner":
        raise DomainError(403, "owner_required", "只有所有者可以撤销授权")
    grant = db.get(SubjectGrant, grant_id)
    if grant is None or grant.revoked_at is not None:
        raise DomainError(404, "grant_not_found", "授权不存在")
    grant.revoked_at = _now()
    db.commit()


def list_grants(db: Session) -> list[SubjectGrant]:
    return list(
        db.scalars(
            select(SubjectGrant).where(SubjectGrant.revoked_at.is_(None))
        ).all()
    )


def user_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


def token_header(request_headers: Any) -> str:
    token = (request_headers.get("x-biolearn-token") or "").strip()
    if token:
        return token
    authorization = (request_headers.get("authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
