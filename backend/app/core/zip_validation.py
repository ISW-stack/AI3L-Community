"""ZIP archive security validation.

Checks for:
- Valid ZIP structure
- Zip bombs (compression ratio, nested ZIPs, total uncompressed size)
- Mac junk files (__MACOSX, .DS_Store, ._* resource forks)
- Path traversal (../ in entry names)
- Dangerous file extensions (.exe, .bat, .js, etc.)
- Entry count limits
"""

import zipfile
from io import BytesIO

from app.core.errors import AppError, ErrorCode

# Maximum allowed decompression ratio (uncompressed / compressed)
MAX_COMPRESSION_RATIO = 100

# Maximum total uncompressed size (1 GB)
MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024

# Maximum number of entries in a ZIP
MAX_ZIP_ENTRIES = 1000

# Mac-specific junk path prefixes and filenames
_MAC_JUNK_PREFIXES = ("__MACOSX/", "__MACOSX\\")
_MAC_JUNK_NAMES = {".DS_Store", "._.DS_Store", "Thumbs.db", "desktop.ini"}

# Dangerous file extensions that should never appear inside uploaded ZIPs
_DANGEROUS_EXTENSIONS = frozenset(
    {
        # Executables / scripts
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".msi",
        ".scr",
        ".pif",
        ".ps1",
        ".vbs",
        ".vbe",
        ".wsf",
        ".wsh",
        ".js",
        ".jse",
        ".sh",
        ".bash",
        ".csh",
        # Dynamic libraries
        ".dll",
        ".so",
        ".dylib",
        # Java / Android
        ".jar",
        ".apk",
        ".class",
        # Office macros
        ".xlsm",
        ".xlsb",
        ".docm",
        ".pptm",
        # Shortcuts / links
        ".lnk",
        ".url",
        ".desktop",
        # Archives that could be nested bombs
        ".zip",
        ".7z",
        ".rar",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".cab",
    }
)


def _is_mac_junk(name: str) -> bool:
    """Check if a ZIP entry is Mac-specific junk."""
    if any(name.startswith(p) for p in _MAC_JUNK_PREFIXES):
        return True
    basename = name.rsplit("/", 1)[-1] if "/" in name else name
    if basename in _MAC_JUNK_NAMES:
        return True
    if basename.startswith("._"):
        return True
    return False


def _get_extension(name: str) -> str:
    """Extract lowercase file extension from a path."""
    basename = name.rsplit("/", 1)[-1] if "/" in name else name
    if "." in basename:
        return "." + basename.rsplit(".", 1)[-1].lower()
    return ""


def _has_path_traversal(name: str) -> bool:
    """Check if entry name attempts path traversal."""
    normalized = name.replace("\\", "/")
    if normalized.startswith("/"):
        return True
    parts = normalized.split("/")
    return ".." in parts


class ZipValidationResult:
    """Result of ZIP validation with optional list of stripped Mac junk entries."""

    __slots__ = ("clean_data", "stripped_entries", "total_entries", "total_uncompressed")

    def __init__(
        self,
        clean_data: bytes | None,
        stripped_entries: list[str],
        total_entries: int,
        total_uncompressed: int,
    ) -> None:
        self.clean_data = clean_data
        self.stripped_entries = stripped_entries
        self.total_entries = total_entries
        self.total_uncompressed = total_uncompressed


def validate_zip(data: bytes, *, strip_mac_junk: bool = True) -> ZipValidationResult:
    """Validate a ZIP archive for security issues.

    Args:
        data: Raw ZIP file bytes.
        strip_mac_junk: If True, rebuild the ZIP without Mac junk entries.

    Returns:
        ZipValidationResult with optionally cleaned data.

    Raises:
        AppError: On any validation failure.
    """
    # 1. Check valid ZIP
    if not zipfile.is_zipfile(BytesIO(data)):
        raise AppError(ErrorCode.ALBUM_003, 400, "File is not a valid ZIP archive.")

    try:
        zf = zipfile.ZipFile(BytesIO(data), "r")
    except zipfile.BadZipFile as exc:
        raise AppError(ErrorCode.ALBUM_003, 400, f"Corrupted ZIP archive: {exc}") from exc

    with zf:
        entries = zf.infolist()

        # 2. Entry count limit
        if len(entries) > MAX_ZIP_ENTRIES:
            raise AppError(
                ErrorCode.ALBUM_003,
                400,
                f"ZIP contains too many entries ({len(entries)}). Maximum is {MAX_ZIP_ENTRIES}.",
            )

        total_uncompressed = 0
        mac_junk_entries: list[str] = []
        has_non_junk = False

        for info in entries:
            name = info.filename

            # 3. Path traversal check
            if _has_path_traversal(name):
                raise AppError(
                    ErrorCode.ALBUM_003,
                    400,
                    "ZIP contains entries with path traversal sequences.",
                )

            # Track Mac junk
            if _is_mac_junk(name):
                mac_junk_entries.append(name)
                continue

            # Skip directories
            if info.is_dir():
                has_non_junk = True
                continue

            has_non_junk = True

            # 4. Dangerous extension check
            ext = _get_extension(name)
            if ext in _DANGEROUS_EXTENSIONS:
                raise AppError(
                    ErrorCode.ALBUM_003,
                    400,
                    f"ZIP contains a potentially dangerous file type ({ext}).",
                )

            # 5. Accumulate uncompressed size
            total_uncompressed += info.file_size

            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise AppError(
                    ErrorCode.ALBUM_003,
                    400,
                    "ZIP total uncompressed size exceeds the 1 GB safety limit.",
                )

            # 6. Per-entry compression ratio check
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_COMPRESSION_RATIO:
                    raise AppError(
                        ErrorCode.ALBUM_003,
                        400,
                        "ZIP contains an entry with a suspiciously high compression ratio (possible zip bomb).",
                    )

        # 7. All-junk ZIP
        if not has_non_junk and mac_junk_entries:
            raise AppError(
                ErrorCode.ALBUM_003,
                400,
                "ZIP contains only Mac system files (__MACOSX / .DS_Store). "
                "Please re-create the archive without these files.",
            )

        # 8. Strip Mac junk if requested and present
        clean_data: bytes | None = None
        if strip_mac_junk and mac_junk_entries:
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
                for info in entries:
                    if info.filename in mac_junk_entries:
                        continue
                    # Copy entry data preserving compression
                    out_zf.writestr(info, zf.read(info.filename))
            clean_data = buf.getvalue()
        else:
            clean_data = data

    return ZipValidationResult(
        clean_data=clean_data,
        stripped_entries=mac_junk_entries,
        total_entries=len(entries) - len(mac_junk_entries),
        total_uncompressed=total_uncompressed,
    )
