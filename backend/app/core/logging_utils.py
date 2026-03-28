"""Utilities for sanitizing PII in log statements."""

import hashlib
import logging
import re

logger = logging.getLogger(__name__)

# Patterns that suggest internal details leaked into exception messages
_SENSITIVE_PATTERNS = re.compile(
    r"("
    r"/[a-z_]+\.py"  # file paths
    r"|(?i:traceback)"  # Python tracebacks
    r"|SELECT \S+ FROM |INSERT INTO |UPDATE \S+ SET |DELETE FROM "  # SQL (uppercase)
    r"|(?i:asyncpg\.|psycopg|sqlalchemy)"  # DB driver names
    r"|(?i:ConnectionRefused)"  # connection errors
    r"|DETAIL:|HINT:"  # PostgreSQL error annotations
    r")",
)

_MAX_USER_MSG_LEN = 300


def safe_error_detail(exc: Exception, fallback: str) -> str:
    """Return a user-safe error message, logging the original for debugging.

    If the exception message looks like it contains internal details (SQL,
    file paths, tracebacks), return *fallback* instead and log the real
    message at WARNING level.
    """
    msg = str(exc)
    if not msg or len(msg) > _MAX_USER_MSG_LEN or _SENSITIVE_PATTERNS.search(msg):
        logger.warning("Sanitised error detail (original suppressed): %s", msg, exc_info=True)
        return fallback
    return msg


def mask_pii(value: str, keep_chars: int = 3) -> str:
    """Mask a PII string, keeping only the first few characters.

    Examples:
        mask_pii("Alice Smith") -> "Ali***"
        mask_pii("AB") -> "***"
        mask_pii("") -> "***"
    """
    if not value or len(value) <= keep_chars:
        return "***"
    return value[:keep_chars] + "***"


def hash_identifier(value: str) -> str:
    """One-way hash an identifier for log correlation without exposing PII.

    Returns a 12-character hex string derived from SHA-256.
    """
    return hashlib.sha256(value.encode()).hexdigest()[:12]
