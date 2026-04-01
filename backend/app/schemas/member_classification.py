from __future__ import annotations

from pydantic import BaseModel, Field


class ClassifiedMemberResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    avatar_url: str | None = None


class CategoryResponse(BaseModel):
    key: str
    label: str
    count: int
    members: list[ClassifiedMemberResponse] = Field(default_factory=list)


class ClassifiedMembersResponse(BaseModel):
    categories: list[CategoryResponse]


class ClassificationAssignRequest(BaseModel):
    user_id: str
    category: str = Field(
        ...,
        pattern=r"^(chair|co_chair|ec_member|sig_chair|sre|member)$",
        description="One of: chair, co_chair, ec_member, sig_chair, sre, member",
    )
    display_order: int = Field(default=0, ge=0, le=999)


class CategoryDetailResponse(BaseModel):
    key: str
    label: str
    members: list[ClassifiedMemberResponse]
