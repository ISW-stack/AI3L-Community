from enum import Enum

from fastapi import HTTPException


class ErrorCode(str, Enum):
    AUTH_001 = "AUTH_001"  # Token expired / invalid / missing session
    AUTH_002 = "AUTH_002"  # Token in blacklist (revoked)
    AUTH_003 = "AUTH_003"  # Guest limit reached
    AUTH_004 = "AUTH_004"  # Account banned
    SYS_403 = "SYS_403"   # Forbidden
    SYS_404 = "SYS_404"   # Not found
    SYS_422 = "SYS_422"   # Validation error
    SYS_409 = "SYS_409"   # Version / idempotency conflict
    SYS_429 = "SYS_429"   # Rate limit exceeded
    FILE_001 = "FILE_001"  # Invalid magic number / malware
    FORM_001 = "FORM_001"  # Form deadline passed


class AppError(HTTPException):
    def __init__(self, code: ErrorCode, status_code: int, detail: str):
        super().__init__(
            status_code=status_code,
            detail={"code": code.value, "message": detail},
        )


class NotFoundError(AppError):
    def __init__(self, entity: str, id: str | None = None):
        detail = f"{entity} not found" if id is None else f"{entity} ({id}) not found"
        super().__init__(ErrorCode.SYS_404, 404, detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(ErrorCode.SYS_403, 403, detail)


class ConflictError(AppError):
    def __init__(self, detail: str):
        super().__init__(ErrorCode.SYS_409, 409, detail)


class RateLimitError(AppError):
    def __init__(self, detail: str = "Too many requests. Try again later."):
        super().__init__(ErrorCode.SYS_429, 429, detail)


class ValidationError(AppError):
    def __init__(self, detail: str):
        super().__init__(ErrorCode.SYS_422, 422, detail)
