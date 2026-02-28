from enum import Enum

from fastapi import HTTPException


class ErrorCode(str, Enum):
    AUTH_001 = "AUTH_001"  # Token expired / invalid / missing session
    AUTH_002 = "AUTH_002"  # Token in blacklist (revoked)
    AUTH_003 = "AUTH_003"  # Guest limit reached
    AUTH_004 = "AUTH_004"  # Account banned
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
