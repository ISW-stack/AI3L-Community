from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    key: str
    url: str
    filename: str
    content_type: str
    size: int
    scan_task_id: str | None = None
