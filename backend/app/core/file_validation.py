"""File upload validation: magic number (byte signature) checks and sanitization."""

# Magic number signatures for allowed file types
MAGIC_NUMBERS = {
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "application/pdf": [b"%PDF"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04"
    ],  # DOCX is a ZIP
}

ALLOWED_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_EDITOR_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def validate_magic_number(data: bytes, expected_content_type: str) -> bool:
    """Validate file content matches expected type by checking magic bytes."""
    signatures = MAGIC_NUMBERS.get(expected_content_type)
    if signatures is None:
        return False
    return any(data[:len(sig)] == sig for sig in signatures)


def get_content_type_from_extension(filename: str) -> str | None:
    """Map file extension to content type."""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    return ALLOWED_EXTENSIONS.get(ext)


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML content using bleach. Allows safe tags for rich text."""
    import bleach

    allowed_tags = [
        "p", "br", "strong", "em", "u", "s", "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li", "blockquote", "pre", "code", "a", "img",
        "table", "thead", "tbody", "tr", "th", "td",
        "span", "div", "sub", "sup", "hr",
    ]
    allowed_attrs = {
        "a": ["href", "title", "target", "rel"],
        "img": ["src", "alt", "width", "height"],
        "span": ["style"],
        "td": ["colspan", "rowspan"],
        "th": ["colspan", "rowspan"],
    }
    return bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True,
    )
