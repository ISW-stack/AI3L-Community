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


def validate_docx_structure(data: bytes) -> bool:
    """Verify that a ZIP-based file is actually a valid DOCX (OOXML).

    Checks for the required [Content_Types].xml and word/ directory.
    Returns False for JAR, APK, or other ZIP-based files masquerading as DOCX.
    """
    import zipfile

    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = zf.namelist()
            has_content_types = "[Content_Types].xml" in names
            has_word_dir = any(n.startswith("word/") for n in names)
            return has_content_types and has_word_dir
    except (zipfile.BadZipFile, Exception):
        return False


def validate_xlsx_structure(data: bytes) -> bool:
    """Verify that a ZIP-based file is actually a valid XLSX.

    M-07: Checks for [Content_Types].xml AND xl/ directory to prevent
    JAR/APK files renamed to .xlsx from passing validation.
    """
    import zipfile

    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = zf.namelist()
            has_content_types = "[Content_Types].xml" in names
            has_xl_dir = any(n.startswith("xl/") for n in names)
            return has_content_types and has_xl_dir
    except (zipfile.BadZipFile, Exception):
        return False


def validate_pptx_structure(data: bytes) -> bool:
    """Verify that a ZIP-based file is actually a valid PPTX.

    M-07: Checks for [Content_Types].xml AND ppt/ directory to prevent
    JAR/APK files renamed to .pptx from passing validation.
    """
    import zipfile

    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = zf.namelist()
            has_content_types = "[Content_Types].xml" in names
            has_ppt_dir = any(n.startswith("ppt/") for n in names)
            return has_content_types and has_ppt_dir
    except (zipfile.BadZipFile, Exception):
        return False


def get_content_type_from_extension(filename: str) -> str | None:
    """Map file extension to content type."""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    return ALLOWED_EXTENSIONS.get(ext)


_PDF_DANGEROUS_KEYS = {
    "/JS", "/JavaScript", "/AA", "/OpenAction",
    "/Launch", "/URI", "/SubmitForm", "/GoToR", "/EmbeddedFiles",
}


def _strip_dangerous_keys_recursive(obj: object, visited: set[int] | None = None) -> None:
    """M-19: Recursively traverse all PDF objects and strip dangerous keys.

    Handles dictionaries (including annotations, embedded files) and arrays.
    Uses a visited set to avoid infinite loops in circular references.
    pikepdf wraps all objects as pikepdf.Object; use _type_code to detect
    the underlying type (dictionary vs array vs other).
    """
    import pikepdf

    if visited is None:
        visited = set()

    obj_id = id(obj)
    if obj_id in visited:
        return
    visited.add(obj_id)

    type_code = getattr(obj, "_type_code", None)

    if type_code == pikepdf.ObjectType.dictionary:
        for key in _PDF_DANGEROUS_KEYS:
            try:
                if key in obj:  # type: ignore[operator]
                    del obj[key]  # type: ignore[arg-type]
            except Exception:
                pass
        try:
            for key in list(obj.keys()):  # type: ignore[union-attr]
                _strip_dangerous_keys_recursive(obj[key], visited)  # type: ignore[index]
        except Exception:
            pass
    elif type_code == pikepdf.ObjectType.array:
        try:
            for item in obj:  # type: ignore[union-attr]
                _strip_dangerous_keys_recursive(item, visited)
        except Exception:
            pass
    elif type_code == pikepdf.ObjectType.stream:
        # Streams have dict-like keys too (e.g. embedded file streams)
        try:
            for key in list(obj.keys()):  # type: ignore[union-attr]
                try:
                    if key in _PDF_DANGEROUS_KEYS:
                        del obj[key]  # type: ignore[arg-type]
                    else:
                        _strip_dangerous_keys_recursive(obj[key], visited)  # type: ignore[index]
                except Exception:
                    pass
        except Exception:
            pass


def sanitize_pdf(data: bytes) -> bytes:
    """Remove JavaScript, auto-actions, and macros from a PDF.

    Uses pikepdf (C++ qpdf engine) for fast, robust PDF manipulation.
    M-19: Recursively traverses ALL PDF objects (annotations, embedded files, etc.)
    """
    import pikepdf

    try:
        pdf = pikepdf.open(BytesIO(data))
    except pikepdf.PdfError as exc:
        raise ValueError(f"Invalid or corrupted PDF: {exc}") from exc

    # Recursively strip dangerous keys from root catalog
    _strip_dangerous_keys_recursive(pdf.Root)

    # Recursively strip dangerous keys from each page (including annotations)
    for page in pdf.pages:
        _strip_dangerous_keys_recursive(page.obj)

    buf = BytesIO()
    pdf.save(buf)
    pdf.close()  # release pikepdf internal structures before returning
    return buf.getvalue()


def strip_exif_metadata(data: bytes, content_type: str) -> bytes:
    """Strip EXIF metadata from images using Pillow.

    M-04: Remove GPS coordinates, camera serial numbers, timestamps, etc.
    Returns the cleaned image bytes. Non-image types are returned unchanged.
    """
    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        return data
    try:
        from PIL import Image

        img = Image.open(BytesIO(data))
        # Create a new image without EXIF data
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        buf = BytesIO()
        fmt = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[content_type]
        clean.save(buf, format=fmt, quality=95 if fmt == "JPEG" else None)
        return buf.getvalue()
    except Exception:
        return data  # Best-effort: return original on failure


def validate_gif_structure(data: bytes) -> bytes:
    """Re-encode GIF via Pillow to strip non-image data (M-03).

    Prevents GIF/HTML polyglot attacks by re-encoding through Pillow,
    which discards any non-GIF payload data.
    """
    try:
        from PIL import Image

        img = Image.open(BytesIO(data))
        if img.format != "GIF":
            raise ValueError("Not a valid GIF image")
        buf = BytesIO()
        # Preserve animation if present
        if getattr(img, "n_frames", 1) > 1:
            frames = []
            durations = []
            for i in range(img.n_frames):
                img.seek(i)
                frames.append(img.copy())
                durations.append(img.info.get("duration", 100))
            frames[0].save(
                buf,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=img.info.get("loop", 0),
            )
        else:
            img.save(buf, format="GIF")
        return buf.getvalue()
    except Exception as exc:
        raise ValueError(f"Invalid GIF file: {exc}") from exc


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

    # H-02: Deep structure validation for DOCX (prevent ZIP masquerading)
    if expected_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        if not validate_docx_structure(data):
            raise AppError(
                ErrorCode.FILE_001,
                400,
                "Invalid DOCX file structure. File may be corrupted or is not a valid Word document.",
            )

    # M-03: Re-encode GIFs to strip polyglot payloads
    if expected_type == "image/gif":
        try:
            data = validate_gif_structure(data)
        except ValueError as exc:
            raise AppError(ErrorCode.FILE_001, 400, str(exc))

    # Sanitize PDFs
    if expected_type == "application/pdf":
        data = sanitize_pdf(data)

    # M-04: Strip EXIF metadata from images
    data = strip_exif_metadata(data, expected_type)

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


async def trigger_virus_scan(file_key: str, file_data: bytes) -> None:
    """Insert a pending scan record and dispatch VirusTotal check.

    Errors are logged but never propagated -- scanning is best-effort
    and must not block uploads.
    """
    import io

    from loguru import logger

    try:
        from app.repositories import file_scan_repo

        await file_scan_repo.insert(file_key)
    except Exception:
        logger.warning("Failed to insert scan record for key=%s", file_key, exc_info=True)

    try:
        from app.tasks.virustotal import check_virustotal, compute_sha256
        from fastapi.concurrency import run_in_threadpool

        file_hash = await run_in_threadpool(compute_sha256, io.BytesIO(file_data))
        check_virustotal.delay(file_hash, file_key)
    except ImportError:
        # VirusTotal / Celery not configured — mark as skipped so the file
        # is not permanently stuck at "pending" and blocked from serving.
        try:
            from app.repositories import file_scan_repo

            await file_scan_repo.update_status(file_key, "skipped")
        except Exception:
            logger.warning("Failed to mark scan as skipped for key=%s", file_key, exc_info=True)
    except Exception:
        logger.warning("VirusTotal scan trigger failed for key=%s", file_key, exc_info=True)
        # Also mark as skipped when task dispatch fails, to avoid stuck "pending".
        try:
            from app.repositories import file_scan_repo

            await file_scan_repo.update_status(file_key, "skipped")
        except Exception:
            pass
