from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class UserSummary(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    status: str
    created_at: datetime
    last_login_at: datetime | None = None


class LoginResponse(BaseModel):
    token: str
    user: UserSummary


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(default="", max_length=120)


class InvitationCreateRequest(BaseModel):
    note: str = Field(default="", max_length=500)


class InvitationRead(BaseModel):
    id: str
    note: str
    role: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None
    invitation_token: str | None = None


class UserStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")


class GrantCreateRequest(BaseModel):
    subject_id: str
    grantee_user_id: str
    permission: str = Field(default="read", pattern="^(read|practice|write)$")


class GrantRead(BaseModel):
    id: str
    subject_id: str
    grantee_user_id: str
    permission: str
    created_at: datetime
