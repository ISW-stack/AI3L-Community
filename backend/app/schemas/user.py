import re
import uuid

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    MAX_AFFILIATION_LENGTH,
    MAX_BIO_LENGTH,
    MAX_DISPLAY_NAME_LENGTH,
    MAX_ORCID_LENGTH,
)

_DANGEROUS_CHARS_RE = re.compile(r"[\x00-\x1f\u200b\u200c\u200d\u202e\ufeff]")


def _validate_display_name_chars(v: str) -> str:
    """Reject control characters and zero-width characters in display names."""
    if _DANGEROUS_CHARS_RE.search(v):
        raise ValueError(
            "Display name must not contain control characters " "or zero-width characters."
        )
    return v


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
    created_at: str | None = None
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


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    bio: str | None = Field(None, max_length=MAX_BIO_LENGTH)
    affiliation: str | None = Field(None, max_length=MAX_AFFILIATION_LENGTH)
    orcid: str | None = Field(None, max_length=MAX_ORCID_LENGTH)
    preferred_language: str | None = Field(
        None, max_length=10, pattern="^(en|zh-TW|zh-CN|ja|fr|es|de|ar|hi|id|it|ko|nan|pt|ru|tr|vi)$"
    )

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_display_name_chars(v)
        return v


class CreateAccountRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    invite_code: str = Field(..., min_length=1, max_length=64)
    captcha_id: str = Field(..., max_length=100)
    captcha_code: str = Field(..., max_length=10)

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, v: str) -> str:
        return _validate_display_name_chars(v)


class ApplyMemberRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=500)

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, v: str) -> str:
        return _validate_display_name_chars(v)


class AdminCreateAccountRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="MEMBER", pattern="^(MEMBER|ADMIN)$")

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, v: str) -> str:
        return _validate_display_name_chars(v)


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern="^(SUPER_ADMIN|ADMIN|MEMBER)$")


class BanRequest(BaseModel):
    reason: str = Field(..., max_length=500)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class BulkRoleChangeRequest(BaseModel):
    user_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)
    role: str = Field(..., pattern="^(MEMBER|ADMIN)$")


class AdminDeleteUserRequest(BaseModel):
    reason: str = Field("", max_length=500)


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
