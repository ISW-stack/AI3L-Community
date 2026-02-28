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
    token: str
    role: str
    expires_in: int  # seconds


class InviteCodeResponse(BaseModel):
    invite_code: str
    expires_at: str


class MessageResponse(BaseModel):
    status: str = "success"
    message: str = ""
