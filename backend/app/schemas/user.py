import uuid

from pydantic import BaseModel, Field

from app.core.constants import (
    MAX_AFFILIATION_LENGTH,
    MAX_BIO_LENGTH,
    MAX_DISPLAY_NAME_LENGTH,
    MAX_ORCID_LENGTH,
)


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    avatar_url: str | None = None
    orcid: str | None = None
    affiliation: str | None = None
    bio: str | None = None
    preferred_language: str = "en"
    is_banned: bool = False
    ban_reason: str | None = None
    preferences: dict | None = None


class PublicUserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    avatar_url: str | None = None
    bio: str | None = None
    affiliation: str | None = None
    orcid: str | None = None
    profile_view_count_unique: int = 0
    profile_view_count_total: int = 0
    created_at: str
    dm_friends_only: bool = False


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(None, max_length=MAX_DISPLAY_NAME_LENGTH)
    bio: str | None = Field(None, max_length=MAX_BIO_LENGTH)
    affiliation: str | None = Field(None, max_length=MAX_AFFILIATION_LENGTH)
    orcid: str | None = Field(None, max_length=MAX_ORCID_LENGTH)
    preferred_language: str | None = Field(
        None, max_length=10, pattern="^(en|zh-TW|zh-CN|ja|fr|es|de)$"
    )


class CreateAccountRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., max_length=100)
    invite_code: str = Field(..., min_length=1)
    captcha_id: str
    captcha_code: str


class ApplyMemberRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)


class AdminCreateAccountRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., max_length=100)
    role: str = Field(default="MEMBER", pattern="^(MEMBER|ADMIN)$")


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern="^(SUPER_ADMIN|ADMIN|MEMBER)$")


class BanRequest(BaseModel):
    reason: str = Field(..., max_length=500)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class BulkRoleChangeRequest(BaseModel):
    user_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)
    role: str = Field(..., pattern="^(MEMBER|ADMIN)$")


class AdminDeleteUserRequest(BaseModel):
    reason: str = Field("", max_length=500)


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
