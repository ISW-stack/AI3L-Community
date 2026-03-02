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
}

ALLOWED_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def validate_magic_number(data: bytes, expected_content_type: str) -> bool:
    """Validate file content matches expected type by checking magic bytes."""
    signatures = MAGIC_NUMBERS.get(expected_content_type)
    if signatures is None:
        return False
    return any(data[: len(sig)] == sig for sig in signatures)


def get_content_type_from_extension(filename: str) -> str | None:
    """Map file extension to content type."""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    return ALLOWED_EXTENSIONS.get(ext)


_PDF_DANGEROUS_KEYS = {"/JS", "/JavaScript", "/AA", "/OpenAction"}


def sanitize_pdf(data: bytes) -> bytes:
    """Remove JavaScript, auto-actions, and macros from a PDF."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(BytesIO(data))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    # Copy metadata
    if reader.metadata:
        writer.add_metadata(reader.metadata)

    # Strip dangerous keys from the root object
    if hasattr(writer, "_root_object"):
        for key in _PDF_DANGEROUS_KEYS:
            if key in writer._root_object:
                del writer._root_object[key]

    # Strip dangerous keys from each page
    for page in writer.pages:
        for key in _PDF_DANGEROUS_KEYS:
            if key in page:
                del page[key]

    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def validate_avatar(content_type: str, data: bytes) -> None:
    """Validate avatar file: type, size, and magic bytes. Raises HTTPException if invalid."""
    from fastapi import HTTPException, status

    from app.core.errors import AppError, ErrorCode

    if content_type not in AVATAR_ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PNG and JPEG images are allowed.",
        )
    if len(data) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 2MB limit.",
        )
    if not validate_magic_number(data, content_type):
        raise AppError(
            ErrorCode.FILE_001,
            400,
            "File content does not match its declared type (invalid magic number).",
        )


def validate_editor_file(filename: str, data: bytes) -> tuple[str, bytes]:
    """Validate + sanitize an editor upload. Returns (content_type, sanitized_data).

    Raises HTTPException or AppError if invalid.
    """
    from fastapi import HTTPException, status

    from app.core.errors import AppError, ErrorCode

    expected_type = get_content_type_from_extension(filename)
    if expected_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type not allowed. Accepted: .png, .jpg, .jpeg, .pdf, .docx",
        )
    if len(data) > MAX_EDITOR_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 20MB limit.",
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
        "a": {"href", "title", "target"},
        "img": {"src", "alt", "width", "height"},
        "td": {"colspan", "rowspan"},
        "th": {"colspan", "rowspan"},
    }
    return nh3.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attrs,
    )
