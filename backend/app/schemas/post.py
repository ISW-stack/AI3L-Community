import uuid

from pydantic import BaseModel, Field, field_validator


def _validate_keyword_length(v: list[str] | None) -> list[str] | None:
    """Shared keyword validator: each keyword must be 50 chars or fewer."""
    if v:
        for kw in v:
            if len(kw) > 50:
                raise ValueError("Each keyword must be 50 characters or fewer.")
    return v


class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1)
    category_id: str | None = None
    sig_id: str | None = None
    keywords: list[str] | None = Field(None, max_length=15)
    allow_comments: bool = True

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: list[str] | None) -> list[str] | None:
        return _validate_keyword_length(v)


class PostUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    content: str | None = Field(None, min_length=1)
    category_id: str | None = None
    keywords: list[str] | None = Field(None, max_length=15)
    allow_comments: bool | None = None
    version: int = Field(..., description="Current version for optimistic locking")

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: list[str] | None) -> list[str] | None:
        return _validate_keyword_length(v)


class PostAuthorResponse(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None


class PostResponse(BaseModel):
    id: str
    title: str
    content: str
    author: PostAuthorResponse
    category_id: str | None = None
    category_name: str | None = None
    sig_id: str | None = None
    sig_name: str | None = None
    keywords: list[str] | None = None
    allow_comments: bool = True
    version: int
    comment_count: int
    is_pinned: bool = False
    view_count: int = 0
    reactions: dict[str, list[str]] | None = None
    last_comment_at: str | None = None
    created_at: str
    updated_at: str


class PostListResponse(BaseModel):
    posts: list[PostResponse]
    # OFFSET mode fields
    total: int | None = None
    current_page: int | None = None
    total_pages: int | None = None
    # Cursor mode fields
    next_cursor: str | None = None
    has_more: bool | None = None


class PostHistoryItem(BaseModel):
    id: str
    version: int
    title: str
    content: str
    edited_at: str


class PostHistoryResponse(BaseModel):
    history: list[PostHistoryItem]
    total: int


class BulkDeletePostsRequest(BaseModel):
    post_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)


class PostSearchRequest(BaseModel):
    keyword: str | None = Field(None, max_length=200)
    category_id: str | None = None
    keywords: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    logic: str = Field(default="AND", pattern="^(AND|OR)$")
    sort: str = Field(default="newest", pattern="^(newest|oldest|most_comments)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PinPostRequest(BaseModel):
    is_pinned: bool
