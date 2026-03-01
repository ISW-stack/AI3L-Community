from pydantic import BaseModel, Field


class CaptchaResponse(BaseModel):
    captcha_id: str
    image_base64: str


class LoginRequest(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=128)
    captcha_id: str
    captcha_code: str = Field(..., max_length=10)


class GuestLoginRequest(BaseModel):
    display_name: str = Field(..., max_length=100)
    captcha_id: str
    captcha_code: str = Field(..., max_length=10)


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
