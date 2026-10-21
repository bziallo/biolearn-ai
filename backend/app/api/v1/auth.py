import hmac

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import _extract_token

router = APIRouter(prefix="/auth", tags=["system"])


class AuthStatus(BaseModel):
    required: bool
    authenticated: bool


@router.get("", response_model=AuthStatus, summary="Whether this server needs an access token")
def auth_status(request: Request) -> AuthStatus:
    settings = get_settings()
    if not settings.auth_required:
        return AuthStatus(required=False, authenticated=True)
    provided = _extract_token(request)
    expected = settings.access_token.get_secret_value().strip()  # type: ignore[union-attr]
    return AuthStatus(
        required=True,
        authenticated=bool(provided) and hmac.compare_digest(provided, expected),
    )
