from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def validate_choice_options(self) -> "QuestionSchema":
        """Ensure choice-type questions have at least 2 options."""
        choice_types = {"single_choice", "multiple_choice", "dropdown"}
        if self.type in choice_types:
            if not self.options or len(self.options) < 2:
                raise ValueError(
                    f"Question '{self.label}' of type '{self.type}' "
                    f"requires at least 2 options."
                )
        return self


class FormCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    banner_url: str | None = None
    deadline: datetime | None = None
    max_respondents: int | None = Field(None, gt=0)
    questions: list[QuestionSchema] = Field(..., min_length=1)
    allow_non_members: bool = False


class FormUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    banner_url: str | None = None
    deadline: datetime | None = None
    max_respondents: int | None = Field(None, gt=0)
    questions: list[QuestionSchema] | None = None
    allow_non_members: bool | None = None


class FormResponseSchema(BaseModel):
    id: str
    sig_id: str | None = None
    title: str
    description: str | None = None
    banner_url: str | None = None
    deadline: str | None = None
    max_respondents: int | None = None
    questions: list[dict[str, Any]]
    is_schema_locked: bool
    allow_non_members: bool = False
    response_count: int
    has_responded: bool = False
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


class FormUserResponseSchema(BaseModel):
    id: str
    form_id: str
    user_id: str
    answers: dict[str, Any]
    created_at: str


class QuestionStatsSchema(BaseModel):
    question_id: str
    question_type: str
    question_label: str
    stats: dict[str, Any]


class FormStatsResponse(BaseModel):
    form_id: str
    total_responses: int
    question_stats: list[QuestionStatsSchema]


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    download_url: str | None = None
    result: dict | None = None
