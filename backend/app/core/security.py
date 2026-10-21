from __future__ import annotations

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.authz import (
    Principal,
    LEGACY_PRINCIPAL,
    principal_from_user,
    reset_current_principal,
    set_current_principal,
)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.auth import resolve_session, token_header

# Health is needed before login; auth endpoints must be reachable anonymously.
PUBLIC_PATHS = {
    "/api/v1/health",
    "/api/v1/auth",
    "/api/v1/auth/login",
    "/api/v1/auth/invitations/accept",
}
PUBLIC_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/assets/")

# Invited users have a read-only experience plus their own practice.
INVITED_GET_PREFIXES = (
    "/api/v1/subjects",
    "/api/v1/chapters",
    "/api/v1/documents",
    "/api/v1/knowledge-points",
    "/api/v1/questions",
    "/api/v1/practice",
    "/api/v1/auth/me",
)
OWNER_ONLY_PREFIXES = (
    "/api/v1/ai",
    "/api/v1/imports",
    "/api/v1/knowledge-jobs",
    "/api/v1/questions/generation-jobs",
    "/api/v1/admin",
)


class AccessTokenMiddleware(BaseHTTPMiddleware):
    """Authentication middleware.

    - No users yet: legacy shared-token mode (or open local mode) is kept so the
      initial owner can be created by a local script and old tests still run.
    - At least one user: all business routes need a valid session; invited users
      are restricted to reads plus their own practice. Owner-only endpoints are
      rejected for invited users before they reach a handler.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        settings = get_settings()

        if request.method == "OPTIONS":
            return await call_next(request)
        if not path.startswith("/api/"):
            return await call_next(request)
        if path == "/api/v1/health" or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        session_factory = getattr(request.app.state, "session_factory", SessionLocal)
        with session_factory() as db:
            from app.core.authz import users_exist

            try:
                accounts_mode = users_exist(db)
            except OperationalError:
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": {
                            "code": "database_migration_required",
                            "message": "数据库尚未升级到账户版本，请先运行 Alembic 迁移",
                        }
                    },
                )

            if not accounts_mode:
                # Historical behaviour: optional global shared token.
                if settings.auth_required:
                    if not self._legacy_path_is_public(request):
                        provided = token_header(request.headers)
                        expected = settings.access_token.get_secret_value().strip()  # type: ignore[union-attr]
                        if not provided or not hmac.compare_digest(provided, expected):
                            return self._unauthorized()
                token = set_current_principal(LEGACY_PRINCIPAL)
                try:
                    return await call_next(request)
                finally:
                    reset_current_principal(token)

            if self._accounts_path_is_public(path):
                token = set_current_principal(
                    Principal(None, "anonymous", "user", False)
                )
                try:
                    return await call_next(request)
                finally:
                    reset_current_principal(token)

            provided = token_header(request.headers)
            user = resolve_session(db, provided) if provided else None
            if user is None:
                return self._unauthorized()

            principal = principal_from_user(user)
            if not principal.is_owner and not self._invited_allowed(request):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": {
                            "code": "forbidden",
                            "message": "当前账号没有访问该功能或资源的权限",
                        }
                    },
                )

            token = set_current_principal(principal)
            try:
                return await call_next(request)
            finally:
                reset_current_principal(token)

    @staticmethod
    def _legacy_path_is_public(request: Request) -> bool:
        path = request.url.path
        return (
            request.method == "OPTIONS"
            or path in PUBLIC_PATHS
            or path.startswith(PUBLIC_PREFIXES)
            or path.rstrip("/") == "/api/v1/auth"
        )

    @staticmethod
    def _accounts_path_is_public(path: str) -> bool:
        # SPA shell and assets must load before the login screen can render.
        if not path.startswith("/api/"):
            return True
        return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)

    @staticmethod
    def _invited_allowed(request: Request) -> bool:
        path = request.url.path
        if any(path.startswith(prefix) for prefix in OWNER_ONLY_PREFIXES):
            return False
        if path.endswith("/jobs"):
            return False
        method = request.method.upper()
        if method in {"GET", "HEAD", "OPTIONS"}:
            return any(path.startswith(prefix) for prefix in INVITED_GET_PREFIXES)
        if method == "POST":
            if path in {"/api/v1/practice/sessions", "/api/v1/auth/logout"}:
                return True
            if path.startswith("/api/v1/practice/sessions/") and path.endswith(
                "/submit"
            ):
                return True
        return False

    @staticmethod
    def _unauthorized() -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={
                "detail": {
                    "code": "auth_required",
                    "message": "需要登录：请先使用账号密码登录",
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


def _extract_token(request: Request) -> str:
    """Backward-compatible helper used by older tests/callers."""

    return token_header(request.headers)
