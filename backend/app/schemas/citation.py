from __future__ import annotations

from pydantic import BaseModel, Field


class CitationEntryResponse(BaseModel):
    id: str
    post_id: str
    post_title: str
    author_name: str
    is_self_citation: bool = False
    created_at: str


class CitationListResponse(BaseModel):
    citations: list[CitationEntryResponse]
    total: int


class CitationSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)
