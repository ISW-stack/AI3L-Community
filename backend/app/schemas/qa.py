from __future__ import annotations

from pydantic import BaseModel, Field


class MarkBestAnswerRequest(BaseModel):
    comment_id: str


class VoteRequest(BaseModel):
    vote: int = Field(..., ge=-1, le=1)  # -1, 0 (remove), or 1
