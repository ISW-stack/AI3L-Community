from pydantic import BaseModel, Field


class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1)
    category_id: str | None = None
    sig_id: str | None = None
    keywords: list[str] | None = Field(None, max_length=15)
    allow_comments: bool = True


class PostUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    content: str | None = Field(None, min_length=1)
    category_id: str | None = None
    keywords: list[str] | None = Field(None, max_length=15)
    allow_comments: bool | None = None
    version: int = Field(..., description="Current version for optimistic locking")


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
    keywords: list[str] | None = None
    allow_comments: bool = True
    version: int
    comment_count: int
    created_at: str
    updated_at: str


class PostListResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    current_page: int
    total_pages: int


class PostHistoryItem(BaseModel):
    id: str
    version: int
    title: str
    content: str
    edited_at: str


class PostHistoryResponse(BaseModel):
    history: list[PostHistoryItem]
    total: int


class PostSearchRequest(BaseModel):
    keyword: str | None = Field(None, max_length=200)
    category_id: str | None = None
    keywords: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    logic: str = Field(default="AND", pattern="^(AND|OR)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
