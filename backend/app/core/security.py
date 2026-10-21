from __future__ import annotations

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

# Health is needed to show connection status before a token is entered, and the
# static SPA shell must load so the settings screen can be rendered at all.
PUBLIC_PATHS = {"/api/v1/health"}
PUBLIC_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/assets/")


class AccessTokenMiddleware(BaseHTTPMiddleware):
    """Optional shared-token guard for LAN / external use.

    Disabled when ``ACCESS_TOKEN`` is empty, which keeps the historical
    single-machine behaviour. The token never appears in URLs or logs: it is
    sent as ``Authorization: Bearer <token>`` or ``X-BioLearn-Token``.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        settings = get_settings()
        if not settings.auth_required:
            return await call_next(request)

        path = request.url.path
        if (
            request.method == "OPTIONS"
            or path in PUBLIC_PATHS
            or path.startswith(PUBLIC_PREFIXES)
            or path.rstrip("/").endswith("/api/v1/auth")
        ):
            return await call_next(request)

        provided = _extract_token(request)
        expected = settings.access_token.get_secret_value().strip()  # type: ignore[union-attr]
        if provided and hmac.compare_digest(provided, expected):
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={
                "detail": {
                    "code": "auth_required",
                    "message": "需要访问口令：请在“连接设置”中填写与后端一致的共享口令",
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


def _extract_token(request: Request) -> str:
    header = request.headers.get("x-biolearn-token", "").strip()
    if header:
        return header
    authorization = request.headers.get("authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""
