import os


def _rate_limit(env_key: str, default_max: int, default_window: int) -> tuple[int, int]:
    max_val = int(os.getenv(f"RATE_LIMIT_{env_key}_MAX", str(default_max)))
    window = int(os.getenv(f"RATE_LIMIT_{env_key}_WINDOW", str(default_window)))
    return (max_val, window)


# Rate limits (max_count, window_seconds)
RATE_LIMIT_LOGIN = _rate_limit("LOGIN", 10, 60)
RATE_LIMIT_REGISTER = _rate_limit("REGISTER", 5, 60)
RATE_LIMIT_GUEST = _rate_limit("GUEST", 10, 60)
RATE_LIMIT_COMMENT = _rate_limit("COMMENT", 30, 60)
RATE_LIMIT_REPORT = _rate_limit("REPORT", 5, 60)

# Entity limits
MAX_POSTS_PER_DAY = 50
MAX_COMMENTS_PER_POST = 200
MAX_ACTIVE_FORMS_PER_SIG = 20
MAX_ACTIVE_INVITE_CODES_PER_USER = 5
MAX_GUESTS = 30
MAX_GUESTS_PER_IP = 3
MAX_KEYWORDS = 15

# File sizes
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB
MAX_EDITOR_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

# Allowed types
AVATAR_ALLOWED_TYPES = {"image/png", "image/jpeg"}

# Presigned URL expiry
PRESIGNED_URL_AVATAR_SECONDS = 86400 * 7  # 7 days
PRESIGNED_URL_FILE_SECONDS = 3600  # 1 hour

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# WebSocket
WS_PING_INTERVAL = 30
WS_PING_TIMEOUT = 90
GUEST_SESSION_TIMEOUT = 45 * 60  # 45 minutes

# Captcha
CAPTCHA_TTL = 300
CAPTCHA_LENGTH = 4

# Additional rate limits
RATE_LIMIT_CAPTCHA = _rate_limit("CAPTCHA", 20, 60)
RATE_LIMIT_FILE_UPLOAD = _rate_limit("FILE_UPLOAD", 10, 60)
RATE_LIMIT_FORM_SUBMIT = _rate_limit("FORM_SUBMIT", 5, 60)
RATE_LIMIT_FORM_EXPORT = _rate_limit("FORM_EXPORT", 1, 300)  # 1 per 5 min per form
RATE_LIMIT_INVITE_GEN = _rate_limit("INVITE_GEN", 5, 3600)
RATE_LIMIT_INVITE_VERIFY = _rate_limit("INVITE_VERIFY", 30, 60)
