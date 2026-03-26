from fastapi import APIRouter, Depends, Path, Request, Response, status
from loguru import logger

from app.core.config import settings
from app.core.constants import (
    MAX_ACTIVE_INVITE_CODES_PER_USER,
    RATE_LIMIT_GUEST,
    RATE_LIMIT_INVITE_GEN,
    RATE_LIMIT_INVITE_VERIFY,
    RATE_LIMIT_LOGIN,
    RATE_LIMIT_REGISTER,
)
from app.core.csrf import generate_csrf_token
from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode
from app.core.event_bus import emit
from app.core.rate_limit import check_rate_limit, get_client_ip
from app.core.security import validate_password_policy
from app.schemas.auth import (
    AuthResponse,
    CaptchaResponse,
    GuestLoginRequest,
    InviteCodeResponse,
    LoginRequest,
    MessageResponse,
    WsTicketResponse,
)
from app.schemas.user import CreateAccountRequest
from app.services.auth import (
    authenticate_user,
    consume_invite_code,
    create_invite_code,
    create_session,
    create_ws_ticket,
    decrement_guest_counter,
    decrement_guest_ip_counter,
    destroy_session,
    get_invite_code,
    guest_login,
    increment_guest_ip_counter,
    refresh_session_ttl,
    register_new_user,
)
from app.services.captcha import generate_captcha, verify_captcha
from app.services.privacy_consent import has_consent
from app.services.user import user_exists_by_username

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, token: str, csrf_token: str, max_age: int) -> None:
    """Set HttpOnly access_token cookie and readable csrf_token cookie."""
    domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite=settings.COOKIE_SAMESITE,  # type: ignore[arg-type]
        max_age=max_age,
        path="/",
        domain=domain,
    )

    # CSRF token — NOT HttpOnly so JavaScript can read it
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=bool(settings.COOKIE_SECURE),
        samesite=settings.COOKIE_SAMESITE,  # type: ignore[arg-type]
        max_age=max_age,
        path="/",
        domain=domain,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies."""
    domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None
    response.delete_cookie(key="access_token", path="/", domain=domain)
    response.delete_cookie(key="csrf_token", path="/", domain=domain)


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha(request: Request) -> CaptchaResponse:
    from app.core.constants import RATE_LIMIT_CAPTCHA

    ip = get_client_ip(request) or "unknown"
    if not await check_rate_limit(f"rl:captcha:{ip}", *RATE_LIMIT_CAPTCHA):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    captcha_id, image_base64 = await generate_captcha()
    return CaptchaResponse(captcha_id=captcha_id, image_base64=image_base64)


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, request: Request, response: Response) -> AuthResponse:
    # Rate limit: 10 attempts/minute per IP
    ip = get_client_ip(request) or "unknown"
    if not await check_rate_limit(f"rl:login:{ip}", *RATE_LIMIT_LOGIN):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    # Verify captcha first
    if not await verify_captcha(req.captcha_id, req.captcha_code):
        raise AppError(
            ErrorCode.AUTH_005, status.HTTP_400_BAD_REQUEST, "Invalid or expired captcha."
        )

    # P2: Per-account rate limit to prevent distributed brute-force
    # M-17: Increased from 20 to 50 to reduce targeted lockout risk
    if not await check_rate_limit(f"rl:login:user:{req.username}", 50, 300):
        raise AppError(ErrorCode.SYS_429, 429, "Too many login attempts for this account.")

    user = await authenticate_user(req.username, req.password)
    if user is None:
        raise AppError(ErrorCode.AUTH_010, 401, "Invalid username or password.")

    # Check banned
    if user.get("is_banned"):
        reason = user.get("ban_reason") or "No reason provided"
        raise AppError(ErrorCode.AUTH_004, 403, f"Account is banned: {reason}")

    token, jti, expires_in = await create_session(str(user["id"]), user["role"])

    # Check privacy consent
    needs_consent = not await has_consent(str(user["id"]))

    # Set cookies — CSRF token bound to session JTI
    csrf_token = generate_csrf_token(jti)
    _set_auth_cookies(response, token, csrf_token, expires_in)

    # Audit log (best-effort, via event bus)
    await emit("audit.action", user_id=str(user["id"]), action="LOGIN", ip_address=ip)

    return AuthResponse(role=user["role"], expires_in=expires_in, requires_consent=needs_consent)


@router.post("/guest/{invite_code}", response_model=AuthResponse)
async def login_as_guest(
    req: GuestLoginRequest,
    request: Request,
    response: Response,
    invite_code: str = Path(..., min_length=1, max_length=64),
) -> AuthResponse:
    # Rate limit: 10 attempts/minute per IP
    ip = get_client_ip(request) or "unknown"
    if not await check_rate_limit(f"rl:guest:{ip}", *RATE_LIMIT_GUEST):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    invite = await get_invite_code(invite_code)
    if invite is None:
        raise AppError(
            ErrorCode.AUTH_006, status.HTTP_404_NOT_FOUND, "Invalid or expired invite code."
        )

    if not await verify_captcha(req.captcha_id, req.captcha_code):
        raise AppError(
            ErrorCode.AUTH_005, status.HTTP_400_BAD_REQUEST, "Invalid or expired captcha."
        )

    # Consume invite code (guest has no DB user, so consumed_by stays NULL)
    consumed = await consume_invite_code(invite_code)
    if not consumed:
        raise AppError(
            ErrorCode.AUTH_006, status.HTTP_400_BAD_REQUEST, "Invalid or expired invite code."
        )

    # Per-IP guest session limit (atomic via Lua script)
    if not await increment_guest_ip_counter(ip):
        raise AppError(
            ErrorCode.SYS_429,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many guest sessions from this IP.",
        )

    result = await guest_login(req.display_name)
    if result is None:
        # Undo the per-IP increment since global capacity is full
        await decrement_guest_ip_counter(ip)
        raise AppError(ErrorCode.AUTH_003, 429, "Guest capacity reached. Please try again later.")

    token, jti, expires_in = result

    # Set cookies — CSRF token bound to session JTI
    csrf_token = generate_csrf_token(jti)
    _set_auth_cookies(response, token, csrf_token, expires_in)

    # Guests always see consent modal on each session
    return AuthResponse(role="GUEST", expires_in=expires_in, requires_consent=True)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request, response: Response, current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    ip = get_client_ip(request)

    await destroy_session(
        user_id=current_user["sub"],
        role=current_user["role"],
        jti=current_user["jti"],
    )

    # Decrement atomic guest counter and per-IP counter on guest logout
    if current_user["role"] == "GUEST":
        await decrement_guest_counter()
        if ip:
            await decrement_guest_ip_counter(ip)
        else:
            logger.warning(
                "Guest logout with no IP address — per-IP counter not decremented",
                extra={"user_id": current_user["sub"]},
            )

    _clear_auth_cookies(response)

    # Audit log (best-effort, via event bus)
    await emit("audit.action", user_id=current_user["sub"], action="LOGOUT", ip_address=ip)

    return MessageResponse(message="Logged out successfully.")


@router.post("/register", response_model=AuthResponse)
async def register(req: CreateAccountRequest, request: Request, response: Response) -> AuthResponse:
    # Rate limit: 5 attempts/minute per IP
    ip = get_client_ip(request) or "unknown"
    if not await check_rate_limit(f"rl:register:{ip}", *RATE_LIMIT_REGISTER):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    # Verify captcha
    if not await verify_captcha(req.captcha_id, req.captcha_code):
        raise AppError(
            ErrorCode.AUTH_005, status.HTTP_400_BAD_REQUEST, "Invalid or expired captcha."
        )

    # Validate invite code
    invite = await get_invite_code(req.invite_code)
    if invite is None:
        raise AppError(
            ErrorCode.AUTH_006, status.HTTP_400_BAD_REQUEST, "Invalid or expired invite code."
        )

    # Validate password policy
    error = validate_password_policy(req.password)
    if error:
        raise AppError(ErrorCode.AUTH_007, status.HTTP_400_BAD_REQUEST, error)

    # Check username uniqueness
    if await user_exists_by_username(req.username):
        raise AppError(ErrorCode.AUTH_008, status.HTTP_409_CONFLICT, "Username already exists.")

    # Create user and consume invite code in a single transaction
    try:
        user = await register_new_user(
            username=req.username,
            password=req.password,
            display_name=req.display_name,
            invite_code=req.invite_code,
        )
    except ValueError:
        raise AppError(
            ErrorCode.AUTH_006, status.HTTP_400_BAD_REQUEST, "Invalid or expired invite code."
        )

    token, jti, expires_in = await create_session(str(user["id"]), user["role"])

    # Set cookies — CSRF token bound to session JTI
    csrf_token = generate_csrf_token(jti)
    _set_auth_cookies(response, token, csrf_token, expires_in)

    # New user always requires consent
    return AuthResponse(role=user["role"], expires_in=expires_in, requires_consent=True)


@router.post("/heartbeat", response_model=MessageResponse)
async def heartbeat(
    response: Response, current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    if not await check_rate_limit(f"rl:heartbeat:{current_user['sub']}", 20, 60):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")
    refreshed = await refresh_session_ttl(current_user["sub"], current_user["role"])
    if not refreshed:
        raise AppError(ErrorCode.AUTH_001, 401, "Session not found.")

    # M-18: Re-set CSRF cookie on heartbeat to ensure it stays in sync with
    # the session. The token is deterministic per JTI (by design) — it rotates
    # when the user logs in again (new JTI). This re-set refreshes the cookie
    # max-age, not the token value.
    csrf_token = generate_csrf_token(current_user["jti"])
    domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=bool(settings.COOKIE_SECURE),
        samesite=settings.COOKIE_SAMESITE,  # type: ignore[arg-type]
        path="/",
        domain=domain,
    )

    return MessageResponse(message="Session refreshed.")


@router.post("/ws-ticket", response_model=WsTicketResponse)
async def get_ws_ticket(current_user: dict = Depends(get_current_user)) -> WsTicketResponse:
    """Generate a one-time WebSocket authentication ticket (30s TTL)."""
    if not await check_rate_limit(f"rl:ws_ticket:{current_user['sub']}", 10, 60):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")
    ticket = await create_ws_ticket(current_user)
    return WsTicketResponse(ticket=ticket)


@router.post("/invite-code", response_model=InviteCodeResponse)
async def generate_invite_code(
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> InviteCodeResponse:
    # IP-based rate limit as defense-in-depth
    ip = get_client_ip(request) or "unknown"
    if not await check_rate_limit(f"rl:invite_ip:{ip}", 10, 3600):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    if not await check_rate_limit(f"rl:invite:{current_user['sub']}", *RATE_LIMIT_INVITE_GEN):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    from app.repositories import invite_code_repo

    active_count = await invite_code_repo.count_active_by_user(current_user["sub"])
    if active_count >= MAX_ACTIVE_INVITE_CODES_PER_USER:
        raise AppError(
            ErrorCode.SYS_429,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Maximum active invite codes reached. "
            "Wait for existing codes to expire or be consumed.",
        )

    code, expires_at = await create_invite_code(current_user["sub"])
    return InviteCodeResponse(
        invite_code=code,
        expires_at=expires_at.isoformat(),
    )


@router.get(
    "/invite-code/{code}",
    response_model=MessageResponse,
)
async def verify_invite_code(
    request: Request,
    code: str = Path(..., min_length=1, max_length=64),
) -> MessageResponse:
    ip = get_client_ip(request) or "unknown"
    if not await check_rate_limit(f"rl:invite_verify:{ip}", *RATE_LIMIT_INVITE_VERIFY):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    result = await get_invite_code(code)
    if result is None:
        raise AppError(
            ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Invalid or expired invite code."
        )
    return MessageResponse(message="Invite code is valid.")
