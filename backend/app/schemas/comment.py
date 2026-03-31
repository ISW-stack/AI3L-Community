import uuid as _uuid

from pydantic import BaseModel, Field, field_validator


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: _uuid.UUID | None = None
    mentions: list[str] | None = Field(None, max_length=10)

    @field_validator("mentions")
    @classmethod
    def validate_mention_length(cls, v: list[str] | None) -> list[str] | None:
        if v:
            for item in v:
                if len(item) > 50:
                    raise ValueError("Each mention must be at most 50 characters")
        return v


class CommentAuthorResponse(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None


class CommentResponse(BaseModel):
    id: str
    post_id: str | None = None
    event_id: str | None = None
    content: str
    author: CommentAuthorResponse
    parent_id: str | None = None
    mentions: list[str] | None = None
    reaction_counts: dict[str, int] | None = None
    user_reactions: list[str] | None = None
    vote_score: int = 0
    is_best_answer: bool = False
    created_at: str
    updated_at: str


class CommentListResponse(BaseModel):
    comments: list[CommentResponse]
    total: int
    page: int = 1
    total_pages: int = 1


class CommentUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class ReactionRequest(BaseModel):
    reaction: str = Field(..., pattern="^(LIKE|SMILE|CRY)$")
