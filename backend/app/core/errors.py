from enum import Enum

from fastapi import HTTPException


class ErrorCode(str, Enum):
    AUTH_001 = "AUTH_001"  # Token expired / invalid / missing session
    AUTH_002 = "AUTH_002"  # Token in blacklist (revoked)
    AUTH_003 = "AUTH_003"  # Guest limit reached
    AUTH_004 = "AUTH_004"  # Account banned
    SYS_403 = "SYS_403"  # Forbidden
    SYS_404 = "SYS_404"  # Not found
    SYS_422 = "SYS_422"  # Validation error
    SYS_409 = "SYS_409"  # Version / idempotency conflict
    SYS_429 = "SYS_429"  # Rate limit exceeded
    SYS_500 = "SYS_500"  # Internal server error
    FILE_001 = "FILE_001"  # Invalid magic number / malware
    FORM_001 = "FORM_001"  # Form deadline passed
    ALBUM_001 = "ALBUM_001"  # Album not found / access denied
    ALBUM_002 = "ALBUM_002"  # Photo upload limit exceeded
    ALBUM_003 = "ALBUM_003"  # Invalid file type for album
    SOCIAL_001 = "SOCIAL_001"  # Already friends / duplicate request
    SOCIAL_002 = "SOCIAL_002"  # Block limit exceeded
    SOCIAL_003 = "SOCIAL_003"  # Cannot interact with blocked user
    COAUTHOR_001 = "COAUTHOR_001"  # Co-author limit exceeded
    COAUTHOR_002 = "COAUTHOR_002"  # Already a co-author / duplicate invite
    CITATION_001 = "CITATION_001"  # Invalid citation reference
    QA_001 = "QA_001"  # Not question author (best answer)
    QA_002 = "QA_002"  # Cannot vote on own answer
    QA_003 = "QA_003"  # Question not found


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


class RateLimitError(ValueError):
    """Domain-level rate limit error (not an HTTP exception).

    Raised by service layer; endpoints should catch and map to 429.
    """

    def __init__(self, detail: str = "Too many requests. Try again later."):
        super().__init__(detail)


class ServiceValidationError(ValueError):
    """Domain-level validation error raised by service layer.

    Endpoints should catch and map to 400.
    """

    def __init__(self, detail: str):
        super().__init__(detail)


class ServiceNotFoundError(ValueError):
    """Domain-level not-found error raised by service layer.

    Endpoints should catch and map to 404.
    """

    def __init__(self, detail: str = "Resource not found."):
        super().__init__(detail)


class StorageQuotaError(ValueError):
    """Domain-level storage quota exceeded error.

    Endpoints should catch and map to 400.
    """

    def __init__(self, detail: str = "Storage quota exceeded."):
        super().__init__(detail)


class ValidationError(AppError):
    def __init__(self, detail: str):
        super().__init__(ErrorCode.SYS_422, 422, detail)
