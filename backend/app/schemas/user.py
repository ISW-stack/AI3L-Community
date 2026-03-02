from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    avatar_url: str | None = None
    orcid: str | None = None
    affiliation: str | None = None
    bio: str | None = None
    is_banned: bool = False
    ban_reason: str | None = None


class PublicUserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    avatar_url: str | None = None
    bio: str | None = None
    affiliation: str | None = None
    orcid: str | None = None
    created_at: str


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=500)
    affiliation: str | None = Field(None, max_length=200)
    orcid: str | None = Field(None, max_length=50)


class CreateAccountRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., max_length=100)
    invite_code: str = Field(..., min_length=1)
    captcha_id: str
    captcha_code: str


class ApplyMemberRequest(BaseModel):
    description: str = Field(..., max_length=500)


class AdminCreateAccountRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., max_length=100)
    role: str = Field(default="MEMBER")


class RoleUpdateRequest(BaseModel):
    role: str


class BanRequest(BaseModel):
    reason: str = Field(..., max_length=500)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
