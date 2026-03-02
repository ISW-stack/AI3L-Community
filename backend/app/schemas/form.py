from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class QuestionOption(BaseModel):
    id: str
    label: str


class QuestionSchema(BaseModel):
    id: str
    type: Literal[
        "text",
        "textarea",
        "single_choice",
        "multiple_choice",
        "dropdown",
        "rating",
        "file_upload",
    ]
    label: str
    required: bool = True
    placeholder: str | None = Field(None, max_length=500)
    max_length: int | None = None
    options: list[QuestionOption] | None = None
    min: int | None = None
    max: int | None = None
    labels: dict[str, str] | None = None
    allowed_types: list[str] | None = None
    max_size_mb: int | None = None


class FormCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    banner_url: str | None = None
    deadline: datetime | None = None
    max_respondents: int | None = Field(None, gt=0)
    questions: list[QuestionSchema] = Field(..., min_length=1)


class FormUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = None
    banner_url: str | None = None
    deadline: datetime | None = None
    max_respondents: int | None = Field(None, gt=0)
    questions: list[QuestionSchema] | None = None


class FormResponseSchema(BaseModel):
    id: str
    sig_id: str
    title: str
    description: str | None = None
    banner_url: str | None = None
    deadline: str | None = None
    max_respondents: int | None = None
    questions: list[dict[str, Any]]
    is_schema_locked: bool
    response_count: int
    is_active: bool
    created_by: str
    created_by_name: str
    created_at: str
    updated_at: str
    user_is_sig_admin: bool = False


class FormListResponse(BaseModel):
    forms: list[FormResponseSchema]
    total: int


class FormResponseItem(BaseModel):
    id: str
    form_id: str
    user_id: str
    display_name: str
    username: str
    answers: dict[str, Any]
    created_at: str


class FormResponseListResponse(BaseModel):
    responses: list[FormResponseItem]
    total: int


class FormSubmitRequest(BaseModel):
    answers: dict[str, Any]


class FormSubmitResponse(BaseModel):
    id: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    download_url: str | None = None
