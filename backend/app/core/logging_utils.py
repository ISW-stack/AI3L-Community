"""Utilities for sanitizing PII in log statements."""

import hashlib


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
