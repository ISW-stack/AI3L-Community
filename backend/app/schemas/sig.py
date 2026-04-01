import uuid

from pydantic import BaseModel, Field


class SigCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)


class SigUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)


class SigResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_by: str
    creator_display_name: str | None = None
    member_count: int
    created_at: str


class SigListResponse(BaseModel):
    sigs: list[SigResponse]
    total: int


class SigMemberResponse(BaseModel):
    id: str
    sig_id: str
    user_id: str
    role: str
    display_name: str
    username: str
    avatar_url: str | None = None
    created_at: str


class SigMemberListResponse(BaseModel):
    members: list[SigMemberResponse]
    total: int


class MySigResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_by: str
    creator_display_name: str | None = None
    member_count: int
    created_at: str
    my_role: str


class MySigListResponse(BaseModel):
    sigs: list[MySigResponse]


class SubAdminAssignRequest(BaseModel):
    user_id: uuid.UUID


class SigMyRoleResponse(BaseModel):
    role: str | None
