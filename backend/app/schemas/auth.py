import re

from pydantic import BaseModel, Field, field_validator

_DANGEROUS_CHARS_RE = re.compile(r"[\x00-\x1f\u200b\u200c\u200d\u202e\ufeff]")


class CaptchaResponse(BaseModel):
    captcha_id: str
    image_base64: str


class LoginRequest(BaseModel):
    # Login accepts any input — authenticate_user() handles rejection with
    # a generic "Invalid username or password" to avoid leaking valid formats.
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)
    captcha_id: str = Field(..., max_length=100)
    captcha_code: str = Field(..., max_length=10)


class GuestLoginRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=50)
    captcha_id: str = Field(..., max_length=100)
    captcha_code: str = Field(..., max_length=10)

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, v: str) -> str:
        if _DANGEROUS_CHARS_RE.search(v):
            raise ValueError(
                "Display name must not contain control characters " "or zero-width characters."
            )
        # P3: Strip HTML tags as defense-in-depth against stored XSS
        import re

        v = re.sub(r"<[^>]*>", "", v)
        if not v.strip():
            raise ValueError("Display name must not be empty after sanitization.")
        return v


class TokenResponse(BaseModel):
    """Legacy response format — kept for backward compatibility."""

    token: str
    role: str
    expires_in: int  # seconds
    requires_consent: bool = False


class AuthResponse(BaseModel):
    """Cookie-based auth response — token is sent via HttpOnly cookie, not in body."""

    role: str
    expires_in: int  # seconds
    requires_consent: bool = False


class WsTicketResponse(BaseModel):
    ticket: str


class InviteCodeResponse(BaseModel):
    invite_code: str
    expires_at: str


class MessageResponse(BaseModel):
    status: str = "success"
    message: str = ""


class ErrorResponse(BaseModel):
    code: str
    message: str
