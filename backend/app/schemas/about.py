from datetime import datetime

from pydantic import BaseModel, Field


class ContributorResponse(BaseModel):
    id: str
    display_name: str
    role: str
    avatar_url: str


class ContributorsListResponse(BaseModel):
    contributors: list[ContributorResponse]


class ContributorAdminResponse(BaseModel):
    id: str
    github_username: str
    display_name: str
    role: str
    display_order: int
    avatar_url: str
    created_at: datetime


class ContributorAdminListResponse(BaseModel):
    contributors: list[ContributorAdminResponse]


class ContributorCreateRequest(BaseModel):
    github_username: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=200)
    display_order: int = Field(default=0)


class ContributorUpdateRequest(BaseModel):
    github_username: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, min_length=1, max_length=200)
    display_order: int | None = None
