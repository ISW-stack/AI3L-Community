from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class QuestionOption(BaseModel):
    id: str = Field(..., max_length=100)
    label: str = Field(..., max_length=500)


class QuestionSchema(BaseModel):
    id: str = Field(..., max_length=100)
    type: Literal[
        "text",
        "textarea",
        "single_choice",
        "multiple_choice",
        "dropdown",
        "rating",
        "file_upload",
    ]
    label: str = Field(..., max_length=500)
    required: bool = True
    placeholder: str | None = Field(None, max_length=500)
    max_length: int | None = Field(None, ge=1, le=10000)
    options: list[QuestionOption] | None = Field(None, max_length=50)
    min: int | None = Field(None, ge=0, le=100)
    max: int | None = Field(None, ge=1, le=100)
    labels: dict[str, str] | None = None
    allowed_types: list[str] | None = Field(None, max_length=20)
    max_size_mb: int | None = Field(None, ge=1, le=50)

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return v
        if len(v) > 20:
            raise ValueError("Labels dict must have at most 20 entries.")
        for key, val in v.items():
            if len(key) > 50:
                raise ValueError("Labels key must be at most 50 characters.")
            if len(val) > 500:
                raise ValueError("Labels value must be at most 500 characters.")
        return v

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

    @model_validator(mode="after")
    def validate_rating_min_max(self) -> "QuestionSchema":
        """Ensure rating questions have min < max."""
        if self.type == "rating":
            min_val = self.min if self.min is not None else 1
            max_val = self.max if self.max is not None else 5
            if min_val >= max_val:
                raise ValueError(
                    f"Rating question '{self.label}': min ({min_val}) must be less than max ({max_val})."
                )
        return self


class FormCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    banner_url: str | None = None
    deadline: datetime | None = None
    max_respondents: int | None = Field(None, gt=0)
    questions: list[QuestionSchema] = Field(..., min_length=1, max_length=100)
    allow_non_members: bool = False

    @field_validator("deadline")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime | None) -> datetime | None:
        """F-13: Ensure deadline is timezone-aware to prevent TypeError on comparison."""
        if v is None:
            return v
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("banner_url")
    @classmethod
    def validate_banner_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) > 2048:
            raise ValueError("Banner URL must be 2048 characters or fewer.")
        if not v.startswith(("http://", "https://", "/")):
            raise ValueError("Banner URL must start with http://, https://, or /.")
        return v


class FormUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    banner_url: str | None = None
    deadline: datetime | None = None
    max_respondents: int | None = Field(None, gt=0)
    questions: list[QuestionSchema] | None = Field(None, max_length=100)
    allow_non_members: bool | None = None

    @field_validator("deadline")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime | None) -> datetime | None:
        """F-13: Ensure deadline is timezone-aware to prevent TypeError on comparison."""
        if v is None:
            return v
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("banner_url")
    @classmethod
    def validate_banner_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) > 2048:
            raise ValueError("Banner URL must be 2048 characters or fewer.")
        if not v.startswith(("http://", "https://", "/")):
            raise ValueError("Banner URL must start with http://, https://, or /.")
        return v


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

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > 200:
            raise ValueError("Too many answers (max 200).")
        for key, val in v.items():
            if not key or len(key) > 100:
                raise ValueError("Answer key must be 1-100 characters.")
            if val is None:
                continue
            if isinstance(val, (str, int, float, bool)):
                if isinstance(val, str) and len(val) > 50000:
                    raise ValueError("Answer value too long (max 50000 chars).")
                continue
            if isinstance(val, list):
                if len(val) > 100:
                    raise ValueError("Answer list too long (max 100 items).")
                if not all(isinstance(item, str) for item in val):
                    raise ValueError("Answer list items must be strings.")
                continue
            if isinstance(val, dict):
                if len(str(val)) > 50000:
                    raise ValueError("Answer dict value too large.")
                continue
            raise ValueError(f"Unsupported answer value type: {type(val).__name__}")
        return v


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
