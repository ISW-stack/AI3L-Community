"""Tests for album cover endpoints and service logic."""

import uuid
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EP = "app.api.v1.endpoints.albums"
_SVC = "app.services.album"


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


def _make_album(album_id=None, user_id=None, cover_photo_url=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(album_id or uuid.uuid4()),
        "title": "Test Album",
        "description": "A test album",
        "cover_photo_url": cover_photo_url,
        "created_by": uid,
        "created_by_name": "Test User",
        "is_archived": False,
        "photo_count": 0,
        "member_count": 1,
        "created_at": now,
        "updated_at": now,
    }


# ── PUT /albums/{id}/cover (set from photo) ───────────────────────────────


class TestSetCoverFromPhoto:
    @pytest.mark.anyio
    async def test_set_cover_from_photo_success(self, client):
        """PUT /albums/{id}/cover → 200 for creator."""
        album_id = uuid.uuid4()
        album = _make_album(album_id=album_id, cover_photo_url="http://example.com/cover.jpg")
        try:
            payload, uid = _override_auth("MEMBER")
            with patch(
                f"{_EP}.set_cover_from_photo",
                new_callable=AsyncMock,
                return_value=album,
            ):
                resp = await client.put(
                    f"/api/v1/albums/{album_id}/cover",
                    json={"photo_id": str(uuid.uuid4())},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["cover_photo_url"] is not None
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_set_cover_from_photo_guest_rejected(self, client):
        """PUT /albums/{id}/cover → 403 for GUEST."""
        try:
            _override_auth("GUEST")
            resp = await client.put(
                f"/api/v1/albums/{uuid.uuid4()}/cover",
                json={"photo_id": str(uuid.uuid4())},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_set_cover_missing_photo_id(self, client):
        """PUT /albums/{id}/cover → 422 when photo_id missing."""
        try:
            _override_auth("ADMIN")
            resp = await client.put(
                f"/api/v1/albums/{uuid.uuid4()}/cover",
                json={},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()


# ── POST /albums/{id}/cover (upload cover) ─────────────────────────────────


class TestUploadCover:
    @pytest.mark.anyio
    async def test_upload_cover_success(self, client):
        """POST /albums/{id}/cover → 200 for MEMBER."""
        album_id = uuid.uuid4()
        album = _make_album(album_id=album_id, cover_photo_url="http://example.com/cover.jpg")
        try:
            payload, uid = _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP}.upload_cover",
                    new_callable=AsyncMock,
                    return_value=album,
                ),
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            ):
                # Create a small JPEG-like file
                jpeg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 100
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/cover",
                    files={"file": ("cover.jpg", BytesIO(jpeg_header), "image/jpeg")},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["cover_photo_url"] is not None
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_cover_guest_rejected(self, client):
        """POST /albums/{id}/cover → 403 for GUEST."""
        try:
            _override_auth("GUEST")
            resp = await client.post(
                f"/api/v1/albums/{uuid.uuid4()}/cover",
                files={"file": ("cover.jpg", BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_cover_rate_limited(self, client):
        """POST /albums/{id}/cover → 429 when rate limited."""
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    f"/api/v1/albums/{uuid.uuid4()}/cover",
                    files={"file": ("cover.jpg", BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


# ── Service: set_cover_from_photo ──────────────────────────────────────────


class TestSetCoverFromPhotoService:
    @pytest.mark.anyio
    async def test_set_cover_from_photo_not_found(self):
        """set_cover_from_photo raises 404 when album not found."""
        from app.core.errors import AppError
        from app.services.album import set_cover_from_photo

        with patch(f"{_SVC}.get_pool") as mock_pool:
            conn = AsyncMock()
            conn.fetchrow = AsyncMock(return_value=None)
            pool_inst = MagicMock()
            pool_inst.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
            pool_inst.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_pool.return_value = pool_inst

            with patch(f"{_SVC}.album_repo.find_album_by_id", new_callable=AsyncMock, return_value=None):
                with pytest.raises(AppError) as exc_info:
                    await set_cover_from_photo(
                        album_id=str(uuid.uuid4()),
                        photo_id=str(uuid.uuid4()),
                        user_id=str(uuid.uuid4()),
                        user_role="ADMIN",
                    )
                assert exc_info.value.status_code == 404

    @pytest.mark.anyio
    async def test_set_cover_from_photo_unauthorized(self):
        """set_cover_from_photo raises 403 for non-admin non-creator."""
        from app.core.errors import AppError
        from app.services.album import set_cover_from_photo

        album_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        album_row = {
            "id": album_id,
            "title": "Test",
            "description": None,
            "cover_photo_url": None,
            "created_by": creator_id,
            "created_by_name": "Creator",
            "is_archived": False,
            "photo_count": 0,
            "member_count": 1,
            "created_at": now,
            "updated_at": now,
        }

        with patch(f"{_SVC}.get_pool") as mock_pool:
            conn = AsyncMock()
            pool_inst = MagicMock()
            pool_inst.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
            pool_inst.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_pool.return_value = pool_inst

            with (
                patch(f"{_SVC}.album_repo.find_album_by_id", new_callable=AsyncMock, return_value=album_row),
                patch(f"{_SVC}.album_repo.find_member", new_callable=AsyncMock, return_value=None),
            ):
                with pytest.raises(AppError) as exc_info:
                    await set_cover_from_photo(
                        album_id=str(album_id),
                        photo_id=str(uuid.uuid4()),
                        user_id=str(user_id),
                        user_role="MEMBER",
                    )
                assert exc_info.value.status_code == 403

    @pytest.mark.anyio
    async def test_set_cover_photo_not_in_album(self):
        """set_cover_from_photo raises 404 if photo is in different album."""
        from app.core.errors import AppError
        from app.services.album import set_cover_from_photo

        album_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        album_row = {
            "id": album_id,
            "title": "Test",
            "description": None,
            "cover_photo_url": None,
            "created_by": creator_id,
            "created_by_name": "Creator",
            "is_archived": False,
            "photo_count": 0,
            "member_count": 1,
            "created_at": now,
            "updated_at": now,
        }

        photo_row = {
            "id": uuid.uuid4(),
            "album_id": uuid.uuid4(),  # different album
            "storage_key": "albums/x/photos/y.jpg",
            "uploaded_by": creator_id,
            "uploaded_by_name": "Creator",
            "original_filename": "test.jpg",
            "file_size_bytes": 1024,
            "content_type": "image/jpeg",
            "thumbnail_key": None,
            "description": None,
            "width": None,
            "height": None,
            "is_zip": False,
            "created_at": now,
            "updated_at": now,
        }

        with patch(f"{_SVC}.get_pool") as mock_pool:
            conn = AsyncMock()
            pool_inst = MagicMock()
            pool_inst.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
            pool_inst.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_pool.return_value = pool_inst

            with (
                patch(f"{_SVC}.album_repo.find_album_by_id", new_callable=AsyncMock, return_value=album_row),
                patch(f"{_SVC}.album_repo.find_member", new_callable=AsyncMock, return_value=None),
                patch(f"{_SVC}.album_repo.find_photo_by_id", new_callable=AsyncMock, return_value=photo_row),
            ):
                with pytest.raises(AppError) as exc_info:
                    await set_cover_from_photo(
                        album_id=str(album_id),
                        photo_id=str(uuid.uuid4()),
                        user_id=str(creator_id),
                        user_role="ADMIN",
                    )
                assert exc_info.value.status_code == 404


# ── Service: upload_cover ──────────────────────────────────────────────────


class TestUploadCoverService:
    @pytest.mark.anyio
    async def test_upload_cover_invalid_type(self):
        """upload_cover raises 400 for non-image content type."""
        from app.core.errors import AppError
        from app.services.album import upload_cover

        with pytest.raises(AppError) as exc_info:
            await upload_cover(
                album_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                user_role="ADMIN",
                file_data=b"PK\x03\x04" + b"\x00" * 100,
                filename="file.zip",
                content_type="application/zip",
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_upload_cover_too_large(self):
        """upload_cover raises 400 when file exceeds 5MB limit."""
        from app.core.errors import AppError
        from app.services.album import upload_cover

        with patch(f"{_SVC}.validate_magic_number", return_value=True):
            with pytest.raises(AppError) as exc_info:
                await upload_cover(
                    album_id=str(uuid.uuid4()),
                    user_id=str(uuid.uuid4()),
                    user_role="ADMIN",
                    file_data=b"\xff\xd8\xff\xe0" + b"\x00" * (6 * 1024 * 1024),
                    filename="big.jpg",
                    content_type="image/jpeg",
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_upload_cover_magic_mismatch(self):
        """upload_cover raises 400 when magic bytes don't match content type."""
        from app.core.errors import AppError
        from app.services.album import upload_cover

        with patch(f"{_SVC}.validate_magic_number", return_value=False):
            with pytest.raises(AppError) as exc_info:
                await upload_cover(
                    album_id=str(uuid.uuid4()),
                    user_id=str(uuid.uuid4()),
                    user_role="ADMIN",
                    file_data=b"\x00\x00\x00\x00" + b"\x00" * 100,
                    filename="fake.jpg",
                    content_type="image/jpeg",
                )
            assert exc_info.value.status_code == 400


# ── Converter: cover presigned URL ─────────────────────────────────────────


class TestAlbumConverterCover:
    def test_cover_presigned_url_generated(self):
        """to_album_response generates presigned URL for cover_photo_url storage key."""
        from app.converters.album_converter import to_album_response

        now = datetime.now(timezone.utc)
        row = {
            "id": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "cover_photo_url": "albums/abc/cover/xyz.jpg",
            "created_by": uuid.uuid4(),
            "created_by_name": "Test",
            "is_archived": False,
            "photo_count": 0,
            "member_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        with patch(
            "app.converters.album_converter.generate_presigned_url",
            return_value="http://minio/presigned-cover-url",
        ):
            result = to_album_response(row)
            assert result["cover_photo_url"] == "http://minio/presigned-cover-url"

    def test_cover_none_when_no_key(self):
        """to_album_response returns None cover when no storage key set."""
        from app.converters.album_converter import to_album_response

        now = datetime.now(timezone.utc)
        row = {
            "id": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "cover_photo_url": None,
            "created_by": uuid.uuid4(),
            "created_by_name": "Test",
            "is_archived": False,
            "photo_count": 0,
            "member_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        result = to_album_response(row)
        assert result["cover_photo_url"] is None

    def test_cover_none_on_presigned_failure(self):
        """to_album_response returns None when presigned URL generation fails."""
        from app.converters.album_converter import to_album_response

        now = datetime.now(timezone.utc)
        row = {
            "id": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "cover_photo_url": "albums/abc/cover/xyz.jpg",
            "created_by": uuid.uuid4(),
            "created_by_name": "Test",
            "is_archived": False,
            "photo_count": 0,
            "member_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        with patch(
            "app.converters.album_converter.generate_presigned_url",
            side_effect=Exception("MinIO down"),
        ):
            result = to_album_response(row)
            assert result["cover_photo_url"] is None


# ── Storage key helper ─────────────────────────────────────────────────────


class TestAlbumCoverKey:
    def test_album_cover_key_format(self):
        """album_cover_key returns correct path format."""
        from app.core.storage import album_cover_key

        key = album_cover_key("abc-123", "file-uuid", "jpg")
        assert key == "albums/abc-123/cover/file-uuid.jpg"


# ── Repo: set_cover_photo & find_first_photo_key ──────────────────────────


class TestAlbumRepoFunctions:
    @pytest.mark.anyio
    async def test_set_cover_photo(self):
        """set_cover_photo executes UPDATE and returns True."""
        from app.repositories.album_repo import set_cover_photo

        conn = AsyncMock()
        conn.execute.return_value = "UPDATE 1"

        album_id = uuid.uuid4()
        result = await set_cover_photo(conn, album_id, "albums/x/cover/y.jpg")
        assert result is True
        conn.execute.assert_called_once()

    @pytest.mark.anyio
    async def test_set_cover_photo_not_found(self):
        """set_cover_photo returns False when album not found."""
        from app.repositories.album_repo import set_cover_photo

        conn = AsyncMock()
        conn.execute.return_value = "UPDATE 0"

        result = await set_cover_photo(conn, uuid.uuid4(), "key")
        assert result is False

    @pytest.mark.anyio
    async def test_find_first_photo_key_exists(self):
        """find_first_photo_key returns key when photos exist."""
        from app.repositories.album_repo import find_first_photo_key

        conn = AsyncMock()
        conn.fetchrow.return_value = {"storage_key": "albums/x/photos/y.jpg"}

        result = await find_first_photo_key(conn, uuid.uuid4())
        assert result == "albums/x/photos/y.jpg"

    @pytest.mark.anyio
    async def test_find_first_photo_key_empty(self):
        """find_first_photo_key returns None when no photos."""
        from app.repositories.album_repo import find_first_photo_key

        conn = AsyncMock()
        conn.fetchrow.return_value = None

        result = await find_first_photo_key(conn, uuid.uuid4())
        assert result is None


# ── Auto-set cover on first upload ─────────────────────────────────────────


class TestAutoSetCoverOnUpload:
    @pytest.mark.anyio
    async def test_auto_set_cover_on_first_upload(self):
        """upload_photo sets cover when album has no cover."""
        from app.services.album import upload_photo

        album_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        album_row = {
            "id": album_id,
            "title": "Test",
            "description": None,
            "cover_photo_url": None,
            "created_by": user_id,
            "created_by_name": "Test",
            "is_archived": False,
            "photo_count": 0,
            "member_count": 1,
            "created_at": now,
            "updated_at": now,
        }

        member_row = {
            "id": uuid.uuid4(),
            "role": "ADMIN",
            "status": "ACCEPTED",
        }

        photo_row = {
            "id": uuid.uuid4(),
            "album_id": album_id,
            "uploaded_by": user_id,
            "uploaded_by_name": "Test",
            "storage_key": "albums/x/photos/y.jpg",
            "original_filename": "test.jpg",
            "file_size_bytes": 1024,
            "content_type": "image/jpeg",
            "thumbnail_key": None,
            "description": None,
            "width": None,
            "height": None,
            "is_zip": False,
            "created_at": now,
            "updated_at": now,
        }

        quota_row = {"storage_used_bytes": 0}

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = quota_row
        mock_conn.execute.return_value = "UPDATE 1"

        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = mock_ctx

        # JPEG magic bytes
        file_data = b"\xff\xd8\xff\xe0" + b"\x00" * 100

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(f"{_SVC}.validate_magic_number", return_value=True),
            patch(f"{_SVC}.album_repo.find_album_by_id", new_callable=AsyncMock, return_value=album_row),
            patch(f"{_SVC}.album_repo.find_member", new_callable=AsyncMock, return_value=member_row),
            patch(f"{_SVC}.album_repo.count_photos", new_callable=AsyncMock, return_value=0),
            patch(f"{_SVC}.album_repo.insert_photo", new_callable=AsyncMock, return_value=photo_row),
            patch(f"{_SVC}.album_repo.set_cover_photo", new_callable=AsyncMock, return_value=True) as mock_set_cover,
            patch(f"{_SVC}.album_repo.find_photo_by_id", new_callable=AsyncMock, return_value=photo_row),
            patch("app.core.async_storage.upload_file", new_callable=AsyncMock),
            patch("app.converters.album_converter.generate_presigned_url", return_value="http://url"),
        ):
            await upload_photo(
                album_id=str(album_id),
                user_id=str(user_id),
                file_data=file_data,
                filename="test.jpg",
                content_type="image/jpeg",
            )
            mock_set_cover.assert_called_once()
