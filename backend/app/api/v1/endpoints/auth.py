from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit
from app.core.security import validate_password_policy
from app.schemas.auth import (
    CaptchaResponse,
    GuestLoginRequest,
    InviteCodeResponse,
    LoginRequest,
    MessageResponse,
    TokenResponse,
)
from app.schemas.user import CreateAccountRequest
from app.services.auth import (
    authenticate_user,
    consume_invite_code,
    create_invite_code,
    create_session,
    destroy_session,
    get_invite_code,
    guest_login,
)
from app.services.captcha import generate_captcha, verify_captcha
from app.services.user import create_user, user_exists_by_username

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha() -> CaptchaResponse:
    captcha_id, image_base64 = await generate_captcha()
    return CaptchaResponse(captcha_id=captcha_id, image_base64=image_base64)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request) -> TokenResponse:
    # Rate limit: 10 attempts/minute per IP
    ip = request.client.host if request.client else "unknown"
    if not await check_rate_limit(f"rl:login:{ip}", 10, 60):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    # Verify captcha first
    if not await verify_captcha(req.captcha_id, req.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired captcha.",
        )

    user = await authenticate_user(req.username, req.password)
    if user is None:
        raise AppError(ErrorCode.AUTH_001, 401, "Invalid username or password.")

    # Check banned
    if user.get("is_banned"):
        reason = user.get("ban_reason") or "No reason provided"
        raise AppError(ErrorCode.AUTH_004, 403, f"Account is banned: {reason}")

    token, expires_in = await create_session(str(user["id"]), user["role"])

    # Check privacy consent
    from app.services.privacy_consent import has_consent

    needs_consent = not await has_consent(str(user["id"]))

    # Audit log (best-effort)
    try:
        from app.services.audit import log_action

        ip = request.client.host if request.client else None
        await log_action(str(user["id"]), "LOGIN", ip_address=ip)
    except Exception:
        pass

    return TokenResponse(
        token=token, role=user["role"], expires_in=expires_in, requires_consent=needs_consent
    )


@router.post("/guest/{invite_code}", response_model=TokenResponse)
async def login_as_guest(invite_code: str, req: GuestLoginRequest, request: Request) -> TokenResponse:
    # Rate limit: 10 attempts/minute per IP
    ip = request.client.host if request.client else "unknown"
    if not await check_rate_limit(f"rl:guest:{ip}", 10, 60):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    invite = await get_invite_code(invite_code)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite code.",
        )

    if not await verify_captcha(req.captcha_id, req.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired captcha.",
        )

    result = await guest_login(req.display_name)
    if result is None:
        raise AppError(ErrorCode.AUTH_003, 429, "Guest capacity reached. Please try again later.")

    token, expires_in = result
    # Guests always see consent modal on each session
    return TokenResponse(token=token, role="GUEST", expires_in=expires_in, requires_consent=True)


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, current_user: dict = Depends(get_current_user)) -> MessageResponse:
    await destroy_session(
        user_id=current_user["sub"],
        role=current_user["role"],
        jti=current_user["jti"],
    )

    # Audit log (best-effort)
    try:
        from app.services.audit import log_action

        ip = request.client.host if request.client else None
        await log_action(current_user["sub"], "LOGOUT", ip_address=ip)
    except Exception:
        pass

    return MessageResponse(message="Logged out successfully.")


@router.post("/register", response_model=TokenResponse)
async def register(req: CreateAccountRequest, request: Request) -> TokenResponse:
    # Rate limit: 5 attempts/minute per IP
    ip = request.client.host if request.client else "unknown"
    if not await check_rate_limit(f"rl:register:{ip}", 5, 60):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    # Verify captcha
    if not await verify_captcha(req.captcha_id, req.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired captcha.",
        )

    # Validate invite code
    invite = await get_invite_code(req.invite_code)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite code.",
        )

    # Validate password policy
    error = validate_password_policy(req.password)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Check username uniqueness
    if await user_exists_by_username(req.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists.",
        )

    user = await create_user(
        username=req.username,
        password=req.password,
        display_name=req.display_name,
    )

    # Mark invite code as consumed
    await consume_invite_code(req.invite_code, str(user["id"]))

    token, expires_in = await create_session(str(user["id"]), user["role"])

    # New user always requires consent
    return TokenResponse(
        token=token, role=user["role"], expires_in=expires_in, requires_consent=True
    )


@router.post("/heartbeat", response_model=MessageResponse)
async def heartbeat(current_user: dict = Depends(get_current_user)) -> MessageResponse:
    from app.services.auth import refresh_session_ttl

    refreshed = await refresh_session_ttl(current_user["sub"], current_user["role"])
    if not refreshed:
        raise AppError(ErrorCode.AUTH_001, 401, "Session not found.")
    return MessageResponse(message="Session refreshed.")


@router.post("/invite-code", response_model=InviteCodeResponse)
async def generate_invite_code(
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> InviteCodeResponse:
    code, expires_at = await create_invite_code(current_user["sub"])
    return InviteCodeResponse(
        invite_code=code,
        expires_at=expires_at.isoformat(),
    )


@router.get(
    "/invite-code/{code}",
    response_model=MessageResponse,
)
async def verify_invite_code(code: str) -> MessageResponse:
    result = await get_invite_code(code)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite code.",
        )
    return MessageResponse(message="Invite code is valid.")
