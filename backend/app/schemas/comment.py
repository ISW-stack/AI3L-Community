from pydantic import BaseModel, Field


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: str | None = None
    mentions: list[str] | None = None


class CommentAuthorResponse(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None


class CommentResponse(BaseModel):
    id: str
    post_id: str
    content: str
    author: CommentAuthorResponse
    parent_id: str | None = None
    mentions: list[str] | None = None
    reactions: dict | None = None
    created_at: str
    updated_at: str


class CommentListResponse(BaseModel):
    comments: list[CommentResponse]
    total: int


class CommentUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class ReactionRequest(BaseModel):
    reaction: str = Field(..., pattern="^(LIKE|SMILE|CRY)$")
