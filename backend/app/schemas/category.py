from pydantic import BaseModel, Field


class CategoryResponse(BaseModel):
    id: str
    name: str
    description: str | None = None


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class CategoryListResponse(BaseModel):
    categories: list[CategoryResponse]
    total: int
