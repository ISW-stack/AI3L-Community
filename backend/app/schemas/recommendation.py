from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RecommendedUserResponse(BaseModel):
    id: str
    user_id: str
    display_name: str
    username: str
    avatar_url: str | None = None
    affiliation: str | None = None
    score: float
    reasons: list[dict[str, Any]]
    created_at: str


class RecommendationsListResponse(BaseModel):
    recommendations: list[RecommendedUserResponse]


class DismissRequest(BaseModel):
    user_id: str
