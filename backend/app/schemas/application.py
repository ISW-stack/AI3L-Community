from pydantic import BaseModel, Field


class ApplicationResponse(BaseModel):
    id: str
    user_id: str
    username: str
    display_name: str
    description: str
    status: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    created_at: str


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationResponse]
    total: int


class MyApplicationResponse(BaseModel):
    class Item(BaseModel):
        id: str
        status: str
        created_at: str
        reviewed_at: str | None = None

    application: Item | None = None


class ReviewApplicationRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVED|REJECTED)$")
