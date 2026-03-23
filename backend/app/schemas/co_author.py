from __future__ import annotations

from pydantic import BaseModel, Field

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


class CoAuthorInviteRequest(BaseModel):
    user_id: str = Field(..., pattern=_UUID_PATTERN)
    display_name: str | None = Field(None, max_length=100)


class ExternalCoAuthorRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    affiliation: str | None = Field(None, max_length=200)
    orcid: str | None = Field(None, max_length=30, pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


class CoAuthorResponse(BaseModel):
    id: str
    post_id: str
    user_id: str | None = None
    display_name: str
    affiliation: str | None = None
    orcid: str | None = None
    is_external: bool = False
    status: str
    avatar_url: str | None = None
    invited_at: str
    responded_at: str | None = None


class CoAuthorListResponse(BaseModel):
    co_authors: list[CoAuthorResponse]


class CoAuthorInvitationResponse(BaseModel):
    id: str
    post_id: str
    post_title: str
    invited_by_name: str
    invited_at: str
    status: str


class CoAuthorInvitationListResponse(BaseModel):
    invitations: list[CoAuthorInvitationResponse]
    total: int
