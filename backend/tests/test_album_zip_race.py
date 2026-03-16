"""Tests for album ZIP upload race-condition protection (C1/C2).

Verifies that upload_file_zip:
- Uses SELECT ... FOR UPDATE to serialise concurrent quota checks
- Rejects uploads that would exceed the storage quota
- Enforces SIG membership before allowing uploads
"""

import io
import uuid
import zipfile
from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import AppError


def _make_zip(files: dict[str, bytes]) -> bytes:
    """Create an in-memory ZIP archive from a name->data mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


_SIG_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()
_ALBUM_ID = uuid.uuid4()

# A minimal valid ZIP with a small image-named file
_SMALL_ZIP = _make_zip({"photo.png": b"\x89PNG" + b"\x00" * 100})


class TestQuotaRaceBlocked:
    """Concurrent uploads cannot bypass storage quota thanks to FOR UPDATE."""

    @pytest.mark.anyio
    async def test_quota_check_uses_for_update(self, mock_pool, mock_conn) -> None:
        """upload_file_zip must SELECT ... FOR UPDATE on the user row."""
        # FOR UPDATE query returns storage used
        mock_conn.fetchrow.return_value = {"storage_used_bytes": 0}

        with (
            patch("app.services.album.get_pool", return_value=mock_pool),
            patch("app.services.album.album_repo") as mock_album_repo,
            patch("app.services.album.user_repo"),
            patch("app.services.album.settings") as mock_settings,
            patch("app.core.async_storage.upload_file", new_callable=AsyncMock),
        ):
            mock_settings.MAX_USER_STORAGE_BYTES = 1_073_741_824
            mock_album_repo.find_album_by_id = AsyncMock(
                return_value={"id": _ALBUM_ID, "sig_id": _SIG_ID}
            )
            mock_album_repo.find_member = AsyncMock(
                return_value={"status": "ACCEPTED", "role": "MEMBER"}
            )
            mock_album_repo.insert_photo = AsyncMock(
                return_value={"id": uuid.uuid4(), "storage_key": "test"}
            )
            mock_album_repo.find_photo_by_id = AsyncMock(return_value=None)

            from app.services.album import upload_file_zip

            with patch("app.services.album.to_album_photo_response", return_value={"id": "test"}):
                result = await upload_file_zip(
                    str(_ALBUM_ID), str(_USER_ID), _SMALL_ZIP, "test.zip", "application/zip"
                )

        # Verify transaction was used
        mock_conn.transaction.assert_called()
        # Verify FOR UPDATE was in the fetchrow call
        fetchrow_calls = mock_conn.fetchrow.call_args_list
        for_update_used = any("FOR UPDATE" in str(call) for call in fetchrow_calls)
        assert for_update_used, "upload_file_zip must use SELECT ... FOR UPDATE"


class TestMembershipEnforced:
    """Non-members cannot upload to a SIG album."""

    @pytest.mark.anyio
    async def test_non_member_rejected(self, mock_pool, mock_conn) -> None:
        """upload_file_zip raises error for non-SIG-members."""
        with (
            patch("app.services.album.get_pool", return_value=mock_pool),
            patch("app.services.album.album_repo") as mock_album_repo,
            patch("app.services.album.user_repo"),
            patch("app.services.album.settings") as mock_settings,
        ):
            mock_settings.MAX_USER_STORAGE_BYTES = 1_073_741_824
            mock_album_repo.find_album_by_id = AsyncMock(
                return_value={"id": _ALBUM_ID, "sig_id": _SIG_ID}
            )
            # Not a member
            mock_album_repo.find_member = AsyncMock(return_value=None)

            from app.services.album import upload_file_zip

            with pytest.raises(AppError) as exc_info:
                await upload_file_zip(
                    str(_ALBUM_ID), str(_USER_ID), _SMALL_ZIP, "test.zip", "application/zip"
                )

            assert exc_info.value.status_code == 403


class TestQuotaExceeded:
    """Uploads that would exceed the storage quota are rejected."""

    @pytest.mark.anyio
    async def test_quota_exceeded_returns_error(self, mock_pool, mock_conn) -> None:
        """upload_file_zip raises error when quota would be exceeded."""
        # User has almost maxed out quota
        mock_conn.fetchrow.return_value = {
            "storage_used_bytes": 1_073_741_824 - 10
        }

        with (
            patch("app.services.album.get_pool", return_value=mock_pool),
            patch("app.services.album.album_repo") as mock_album_repo,
            patch("app.services.album.user_repo"),
            patch("app.services.album.settings") as mock_settings,
        ):
            mock_settings.MAX_USER_STORAGE_BYTES = 1_073_741_824
            mock_album_repo.find_album_by_id = AsyncMock(
                return_value={"id": _ALBUM_ID, "sig_id": _SIG_ID}
            )
            mock_album_repo.find_member = AsyncMock(
                return_value={"status": "ACCEPTED", "role": "MEMBER"}
            )

            from app.services.album import upload_file_zip

            with pytest.raises(AppError) as exc_info:
                await upload_file_zip(
                    str(_ALBUM_ID), str(_USER_ID), _SMALL_ZIP, "test.zip", "application/zip"
                )

            assert exc_info.value.status_code == 400
