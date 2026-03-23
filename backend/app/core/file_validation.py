"""File upload validation: magic number (byte signature) checks and sanitization."""

from io import BytesIO

from app.core.constants import (  # noqa: F401
    AVATAR_ALLOWED_TYPES,
    MAX_AVATAR_SIZE,
    MAX_EDITOR_FILE_SIZE,
)

# Magic number signatures for allowed file types
MAGIC_NUMBERS = {
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "application/pdf": [b"%PDF"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04"
    ],  # DOCX is a ZIP
    "image/webp": [b"RIFF"],  # First 4 bytes; validated further in validate_magic_number
    "image/gif": [b"GIF87a", b"GIF89a"],
}

ALLOWED_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def validate_magic_number(data: bytes, expected_content_type: str) -> bool:
    """Validate file content matches expected type by checking magic bytes."""
    signatures = MAGIC_NUMBERS.get(expected_content_type)
    if signatures is None:
        return False
    if not any(data[: len(sig)] == sig for sig in signatures):
        return False
    # WebP requires additional check: bytes 8-12 must be "WEBP"
    if expected_content_type == "image/webp":
        if len(data) < 12 or data[8:12] != b"WEBP":
            return False
    return True


def get_content_type_from_extension(filename: str) -> str | None:
    """Map file extension to content type."""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    return ALLOWED_EXTENSIONS.get(ext)


_PDF_DANGEROUS_KEYS = {"/JS", "/JavaScript", "/AA", "/OpenAction"}


def sanitize_pdf(data: bytes) -> bytes:
    """Remove JavaScript, auto-actions, and macros from a PDF.

    Uses pikepdf (C++ qpdf engine) for fast, robust PDF manipulation.
    """
    import pikepdf

    try:
        pdf = pikepdf.open(BytesIO(data))
    except pikepdf.PdfError as exc:
        raise ValueError(f"Invalid or corrupted PDF: {exc}") from exc

    # Strip dangerous keys from the document root catalog
    for key in _PDF_DANGEROUS_KEYS:
        if key in pdf.Root:
            del pdf.Root[key]

    # Strip dangerous keys from each page
    for page in pdf.pages:
        page_obj = page.obj
        for key in _PDF_DANGEROUS_KEYS:
            if key in page_obj:
                del page_obj[key]

    buf = BytesIO()
    pdf.save(buf)
    pdf.close()  # release pikepdf internal structures before returning
    return buf.getvalue()


def validate_avatar(content_type: str, data: bytes) -> None:
    """Validate avatar file: type, size, and magic bytes. Raises AppError if invalid."""
    from app.core.errors import AppError, ErrorCode

    if content_type not in AVATAR_ALLOWED_TYPES:
        raise AppError(
            ErrorCode.FILE_001,
            400,
            "Only PNG and JPEG images are allowed.",
        )
    if len(data) > MAX_AVATAR_SIZE:
        raise AppError(
            ErrorCode.FILE_001,
            400,
            "File size exceeds 2MB limit.",
        )
    if not validate_magic_number(data, content_type):
        raise AppError(
            ErrorCode.FILE_001,
            400,
            "File content does not match its declared type (invalid magic number).",
        )


def validate_editor_file(filename: str, data: bytes) -> tuple[str, bytes]:
    """Validate + sanitize an editor upload. Returns (content_type, sanitized_data).

    Raises AppError if invalid.
    """
    from app.core.errors import AppError, ErrorCode

    expected_type = get_content_type_from_extension(filename)
    if expected_type is None:
        raise AppError(
            ErrorCode.FILE_001,
            400,
            "File type not allowed. Accepted: .png, .jpg, .jpeg, .pdf, .docx",
        )
    if len(data) > MAX_EDITOR_FILE_SIZE:
        raise AppError(
            ErrorCode.FILE_001,
            400,
            "File size exceeds 10MB limit.",
        )
    if not validate_magic_number(data, expected_type):
        raise AppError(
            ErrorCode.FILE_001,
            400,
            "File content does not match its extension (invalid magic number).",
        )

    # Sanitize PDFs
    if expected_type == "application/pdf":
        data = sanitize_pdf(data)

    return expected_type, data


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML content using nh3. Allows safe tags for rich text."""
    import nh3

    allowed_tags = {
        "p",
        "br",
        "strong",
        "em",
        "u",
        "s",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "blockquote",
        "pre",
        "code",
        "a",
        "img",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "span",
        "div",
        "sub",
        "sup",
        "hr",
    }
    allowed_attrs = {
        "a": {"href", "title", "target", "data-citation"},
        "img": {"src", "alt", "width", "height"},
        "td": {"colspan", "rowspan"},
        "th": {"colspan", "rowspan"},
        "code": {"class"},
        "pre": {"class"},
    }
    return nh3.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        link_rel="noopener noreferrer",
    )


def post_process_citations(html: str) -> str:
    """Add citation class to citation links after sanitization.

    nh3 does not allow adding 'class' to <a> tags (panics), so we add it
    as a post-processing step. Uses regex to handle variations in attribute
    quoting/ordering that nh3 may produce across versions.
    """
    import re

    return re.sub(
        r'data-citation\s*=\s*["\']true["\'](?!\s+class=)',
        r'data-citation="true" class="citation"',
        html,
    )
