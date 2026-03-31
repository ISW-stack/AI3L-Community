from pydantic import BaseModel, Field, field_validator

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_VALID_VISIBILITY = {"GUEST", "MEMBER", "ADMIN"}


class EventCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=100_000)
    sig_id: str | None = Field(None, pattern=_UUID_PATTERN)
    visibility: list[str] = Field(..., min_length=1)
    allow_comments: bool = True

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: list[str]) -> list[str]:
        invalid = set(v) - _VALID_VISIBILITY
        if invalid:
            raise ValueError(f"Invalid visibility values: {invalid}")
        return sorted(set(v))


class EventUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    content: str | None = Field(None, min_length=1, max_length=100_000)
    sig_id: str | None = Field(None, pattern=_UUID_PATTERN)
    visibility: list[str] | None = Field(None, min_length=1)
    allow_comments: bool | None = None
    version: int = Field(..., description="Current version for optimistic locking")

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = set(v) - _VALID_VISIBILITY
            if invalid:
                raise ValueError(f"Invalid visibility values: {invalid}")
            return sorted(set(v))
        return v


class EventAuthorResponse(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None


class EventResponse(BaseModel):
    id: str
    title: str
    content: str
    author: EventAuthorResponse
    sig_id: str | None = None
    sig_name: str | None = None
    visibility: list[str]
    allow_comments: bool
    comment_count: int = 0
    reaction_counts: dict[str, int] | None = None
    user_reactions: list[str] | None = None
    version: int = 1
    created_at: str
    updated_at: str


class EventListResponse(BaseModel):
    events: list[EventResponse]
    total: int = 0
    page: int = 1
    total_pages: int = 1
