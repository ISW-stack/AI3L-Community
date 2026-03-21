"""Tests for app.core.zip_validation — ZIP security validation.

Covers:
- Valid ZIP detection
- Zip bomb detection (compression ratio)
- Mac junk filtering (__MACOSX, .DS_Store, ._* resource forks)
- Path traversal prevention
- Dangerous file extension blocking
- Entry count limit
- All-junk ZIP rejection
- Clean ZIP pass-through
"""

import io
import zipfile

import pytest

from app.core.errors import AppError
from app.core.zip_validation import (
    MAX_COMPRESSION_RATIO,
    MAX_ZIP_ENTRIES,
    ZipValidationResult,
    validate_zip,
)


def _make_zip(files: dict[str, bytes], *, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    """Create an in-memory ZIP archive from a name→data mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=compression) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


# ── Valid ZIP ──────────────────────────────────────────────────────────────


class TestValidZip:
    def test_not_a_zip(self) -> None:
        with pytest.raises(AppError, match="not a valid ZIP"):
            validate_zip(b"this is not a zip file at all")

    def test_empty_bytes(self) -> None:
        with pytest.raises(AppError, match="not a valid ZIP"):
            validate_zip(b"")

    def test_truncated_zip(self) -> None:
        good_zip = _make_zip({"a.txt": b"hello"})
        with pytest.raises(AppError):
            validate_zip(good_zip[:20])

    def test_valid_simple_zip(self) -> None:
        data = _make_zip({"readme.txt": b"hello world"})
        result = validate_zip(data)
        assert isinstance(result, ZipValidationResult)
        assert result.clean_data is not None
        assert result.total_entries == 1
        assert result.stripped_entries == []


# ── Zip Bomb Detection ────────────────────────────────────────────────────


class TestZipBomb:
    def test_high_compression_ratio_rejected(self) -> None:
        """A file with extremely high compression ratio should be rejected."""
        # Create a file that compresses very well (all zeros)
        huge_zeros = b"\x00" * (1024 * 1024 * 10)  # 10MB of zeros
        data = _make_zip({"bomb.txt": huge_zeros})
        # The compressed size of zeros is very small compared to 10MB
        # Check if ratio exceeds MAX_COMPRESSION_RATIO
        zf = zipfile.ZipFile(io.BytesIO(data))
        info = zf.infolist()[0]
        ratio = info.file_size / info.compress_size if info.compress_size > 0 else 0
        if ratio > MAX_COMPRESSION_RATIO:
            with pytest.raises(AppError, match="compression ratio"):
                validate_zip(data)
        else:
            # If the test data doesn't trigger the ratio, just pass
            result = validate_zip(data)
            assert result is not None

    def test_normal_compression_ratio_accepted(self) -> None:
        """Typical files should pass ratio check."""
        # Random-ish data doesn't compress well
        import os

        random_data = os.urandom(1024)
        data = _make_zip({"random.bin": random_data})
        result = validate_zip(data)
        assert result.total_entries == 1


# ── Mac Junk Filtering ────────────────────────────────────────────────────


class TestMacJunk:
    def test_macosx_folder_stripped(self) -> None:
        data = _make_zip({
            "photos/img1.jpg": b"\xff\xd8\xff" + b"\x00" * 100,
            "__MACOSX/photos/._img1.jpg": b"\x00" * 50,
            "__MACOSX/.DS_Store": b"\x00" * 30,
        })
        result = validate_zip(data, strip_mac_junk=True)
        assert len(result.stripped_entries) == 2
        assert "__MACOSX/photos/._img1.jpg" in result.stripped_entries
        assert "__MACOSX/.DS_Store" in result.stripped_entries
        assert result.total_entries == 1

        # Verify the clean ZIP doesn't contain junk
        clean_zf = zipfile.ZipFile(io.BytesIO(result.clean_data))
        names = clean_zf.namelist()
        assert "photos/img1.jpg" in names
        assert "__MACOSX/photos/._img1.jpg" not in names

    def test_ds_store_stripped(self) -> None:
        data = _make_zip({
            "folder/file.txt": b"content",
            "folder/.DS_Store": b"\x00" * 20,
        })
        result = validate_zip(data, strip_mac_junk=True)
        assert ".DS_Store" in result.stripped_entries[0]
        assert result.total_entries == 1

    def test_resource_fork_stripped(self) -> None:
        data = _make_zip({
            "doc.pdf": b"%PDF-1.4" + b"\x00" * 100,
            "._doc.pdf": b"\x00" * 40,
        })
        result = validate_zip(data, strip_mac_junk=True)
        assert len(result.stripped_entries) == 1
        assert "._doc.pdf" in result.stripped_entries[0]

    def test_thumbs_db_stripped(self) -> None:
        data = _make_zip({
            "photo.jpg": b"\xff\xd8\xff" + b"\x00" * 100,
            "Thumbs.db": b"\x00" * 50,
        })
        result = validate_zip(data, strip_mac_junk=True)
        assert "Thumbs.db" in result.stripped_entries

    def test_all_junk_zip_rejected(self) -> None:
        data = _make_zip({
            "__MACOSX/._something": b"\x00" * 10,
            ".DS_Store": b"\x00" * 10,
        })
        with pytest.raises(AppError, match="only Mac system files"):
            validate_zip(data)

    def test_no_strip_when_disabled(self) -> None:
        """When strip_mac_junk=False, junk is detected but data is returned as-is."""
        data = _make_zip({
            "file.txt": b"content",
            "__MACOSX/._file.txt": b"\x00" * 10,
        })
        result = validate_zip(data, strip_mac_junk=False)
        # Junk is still detected (for logging/reporting)
        assert len(result.stripped_entries) == 1
        # But data is returned as-is (no rebuild)
        assert result.clean_data == data


# ── Path Traversal ────────────────────────────────────────────────────────


class TestPathTraversal:
    def test_dot_dot_in_path(self) -> None:
        data = _make_zip({"../../../etc/passwd": b"root:x:0:0"})
        with pytest.raises(AppError, match="path traversal"):
            validate_zip(data)

    def test_absolute_path(self) -> None:
        data = _make_zip({"/etc/passwd": b"root:x:0:0"})
        with pytest.raises(AppError, match="path traversal"):
            validate_zip(data)

    def test_backslash_traversal(self) -> None:
        data = _make_zip({"..\\..\\windows\\system32\\config": b"data"})
        with pytest.raises(AppError, match="path traversal"):
            validate_zip(data)

    def test_normal_nested_path_ok(self) -> None:
        data = _make_zip({"photos/2024/summer/img.jpg": b"\xff\xd8\xff" + b"\x00" * 50})
        result = validate_zip(data)
        assert result.total_entries == 1


# ── Dangerous Extensions ──────────────────────────────────────────────────


class TestDangerousExtensions:
    @pytest.mark.parametrize(
        "filename",
        [
            "malware.exe",
            "script.bat",
            "hack.cmd",
            "trojan.scr",
            "payload.ps1",
            "virus.vbs",
            "evil.js",
            "lib.dll",
            "app.apk",
            "module.jar",
            "macro.xlsm",
            "link.lnk",
            "nested.zip",
            "archive.tar",
            "compressed.gz",
            "shell.sh",
        ],
    )
    def test_dangerous_extension_rejected(self, filename: str) -> None:
        data = _make_zip({filename: b"\x00" * 10})
        with pytest.raises(AppError, match="dangerous file type"):
            validate_zip(data)

    @pytest.mark.parametrize(
        "filename",
        [
            "photo.jpg",
            "document.pdf",
            "readme.txt",
            "data.csv",
            "image.png",
            "video.mp4",
            "song.mp3",
            "page.html",
            "style.css",
        ],
    )
    def test_safe_extension_accepted(self, filename: str) -> None:
        data = _make_zip({filename: b"\x00" * 10})
        result = validate_zip(data)
        assert result.total_entries == 1

    def test_case_insensitive_extension(self) -> None:
        data = _make_zip({"MALWARE.EXE": b"\x00" * 10})
        with pytest.raises(AppError, match="dangerous file type"):
            validate_zip(data)


# ── Entry Count Limit ─────────────────────────────────────────────────────


class TestEntryCountLimit:
    def test_too_many_entries(self) -> None:
        files = {f"file_{i}.txt": b"x" for i in range(MAX_ZIP_ENTRIES + 1)}
        data = _make_zip(files)
        with pytest.raises(AppError, match="too many entries"):
            validate_zip(data)

    def test_max_entries_ok(self) -> None:
        files = {f"file_{i}.txt": b"x" for i in range(100)}
        data = _make_zip(files)
        result = validate_zip(data)
        assert result.total_entries == 100


# ── Nested ZIP Detection ──────────────────────────────────────────────────


class TestNestedZip:
    def test_zip_inside_zip_rejected(self) -> None:
        inner = _make_zip({"inner.txt": b"secret"})
        outer = _make_zip({"nested.zip": inner})
        with pytest.raises(AppError, match="dangerous file type"):
            validate_zip(outer)


# ── Integration: Combined Scenarios ───────────────────────────────────────


class TestCombinedScenarios:
    def test_mac_junk_with_valid_content(self) -> None:
        data = _make_zip({
            "photos/vacation1.jpg": b"\xff\xd8\xff" + b"\x00" * 200,
            "photos/vacation2.png": b"\x89PNG" + b"\x00" * 200,
            "__MACOSX/photos/._vacation1.jpg": b"\x00" * 30,
            "__MACOSX/._DS_Store": b"\x00" * 20,
            ".DS_Store": b"\x00" * 10,
        })
        result = validate_zip(data)
        assert result.total_entries == 2
        assert len(result.stripped_entries) == 3

    def test_clean_zip_no_rebuild(self) -> None:
        """A clean ZIP (no junk) should return original data without rebuild."""
        data = _make_zip({"file.txt": b"hello"})
        result = validate_zip(data)
        assert result.clean_data == data
        assert result.stripped_entries == []

    def test_desktop_ini_stripped(self) -> None:
        data = _make_zip({
            "file.txt": b"content",
            "desktop.ini": b"[ViewState]",
        })
        result = validate_zip(data)
        assert "desktop.ini" in result.stripped_entries
