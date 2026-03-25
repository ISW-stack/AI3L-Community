from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class SiteExportRequest(BaseModel):
    include_database: bool = Field(True, description="Export all database tables as JSON")
    include_files: bool = Field(True, description="Export all S3/R2 stored files")

    @model_validator(mode="after")
    def _at_least_one_option(self) -> SiteExportRequest:
        if not self.include_database and not self.include_files:
            raise ValueError("At least one of include_database or include_files must be True.")
        return self


class SiteExportResponse(BaseModel):
    task_id: str
    message: str


class ExportProgressResponse(BaseModel):
    task_id: str
    status: str  # PENDING / STARTED / SUCCESS / FAILURE
    phase: str | None = None  # db / files / uploading / done
    current: int = 0
    total: int = 0
    detail: str | None = None
    zip_size: int = 0
    download_url: str | None = None
    started_at: str | None = None
    error: str | None = None


class ExportHistoryItem(BaseModel):
    task_id: str
    status: str
    created_at: str
    created_by: str
    options: dict
    file_size: int | None = None
    download_url: str | None = None


class ExportHistoryResponse(BaseModel):
    exports: list[ExportHistoryItem]
    total: int = 0
