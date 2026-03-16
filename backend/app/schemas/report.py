from pydantic import BaseModel, Field


class PostReportCreateRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


class PostReportResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    reason: str
    status: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    created_at: str
    post_title: str | None = None


class PostReportListResponse(BaseModel):
    reports: list[PostReportResponse]
    total: int
    page: int
    total_pages: int


class PostReportReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(RESOLVED|DISMISSED)$")
