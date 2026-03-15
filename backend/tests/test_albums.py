"""Tests for album endpoints — create, list, get, update, delete, members, photos, comments."""

import uuid
from datetime import datetime, timezone
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


def _make_album(album_id=None, user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(album_id or uuid.uuid4()),
        "title": "Test Album",
        "description": "A test album",
        "cover_photo_url": None,
        "created_by": uid,
        "created_by_name": "Test User",
        "is_archived": False,
        "photo_count": 0,
        "member_count": 1,
        "created_at": now,
        "updated_at": now,
    }


def _make_photo(photo_id=None, album_id=None, user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(photo_id or uuid.uuid4()),
        "album_id": str(album_id or uuid.uuid4()),
        "uploaded_by": user_id or str(uuid.uuid4()),
        "uploaded_by_name": "Test User",
        "storage_url": "http://example.com/photo.jpg",
        "thumbnail_url": "http://example.com/thumb.webp",
        "original_filename": "photo.jpg",
        "file_size_bytes": 1024,
        "content_type": "image/jpeg",
        "description": None,
        "width": None,
        "height": None,
        "is_zip": False,
        "created_at": now,
        "updated_at": now,
    }


def _make_comment(comment_id=None, album_id=None, user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(comment_id or uuid.uuid4()),
        "album_id": str(album_id or uuid.uuid4()),
        "photo_id": None,
        "user_id": uid,
        "display_name": "Test User",
        "avatar_url": None,
        "parent_id": None,
        "content": "<p>Nice photo!</p>",
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }


def _make_member(member_id=None, album_id=None, user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(member_id or uuid.uuid4()),
        "album_id": str(album_id or uuid.uuid4()),
        "user_id": uid,
        "display_name": "Test User",
        "username": "testuser",
        "avatar_url": None,
        "role": "MEMBER",
        "status": "ACCEPTED",
        "joined_at": now,
    }


# ── Album CRUD ──────────────────────────────────────────────────────────────


class TestCreateAlbum:
    @pytest.mark.anyio
    async def test_create_album_admin(self, client):
        """POST /albums → 201 for ADMIN."""
        album = _make_album()
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.create_album", new_callable=AsyncMock, return_value=album):
                resp = await client.post(
                    "/api/v1/albums",
                    json={"title": "Test Album", "description": "A test album"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["title"] == "Test Album"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_album_member_rejected(self, client):
        """POST /albums → 403 for MEMBER."""
        try:
            _override_auth("MEMBER")
            resp = await client.post(
                "/api/v1/albums",
                json={"title": "Test Album"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_album_guest_rejected(self, client):
        """POST /albums → 403 for GUEST."""
        try:
            _override_auth("GUEST")
            resp = await client.post(
                "/api/v1/albums",
                json={"title": "Test Album"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestListAlbums:
    @pytest.mark.anyio
    async def test_list_albums(self, client):
        """GET /albums → 200 with paginated list."""
        album = _make_album()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_albums",
                new_callable=AsyncMock,
                return_value=([album], 1),
            ):
                resp = await client.get(
                    "/api/v1/albums",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["albums"]) == 1
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_albums_unauthenticated(self, client):
        """GET /albums without auth → 401."""
        resp = await client.get("/api/v1/albums")
        assert resp.status_code == 401


class TestGetAlbum:
    @pytest.mark.anyio
    async def test_get_album(self, client):
        """GET /albums/{id} → 200."""
        album_id = uuid.uuid4()
        album = _make_album(album_id=album_id)
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.get_album", new_callable=AsyncMock, return_value=album):
                resp = await client.get(
                    f"/api/v1/albums/{album_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["title"] == "Test Album"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_album_not_found(self, client):
        """GET /albums/{id} → 404."""
        from app.core.errors import AppError, ErrorCode

        album_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.get_album",
                new_callable=AsyncMock,
                side_effect=AppError(ErrorCode.ALBUM_001, 404, "Album not found."),
            ):
                resp = await client.get(
                    f"/api/v1/albums/{album_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()


class TestUpdateAlbum:
    @pytest.mark.anyio
    async def test_update_album(self, client):
        """PUT /albums/{id} → 200."""
        album_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        album = _make_album(album_id=album_id, user_id=user_id)
        album["title"] = "Updated Album"
        try:
            _override_auth("ADMIN", user_id=user_id)
            with patch(f"{_EP}.update_album", new_callable=AsyncMock, return_value=album):
                resp = await client.put(
                    f"/api/v1/albums/{album_id}",
                    json={"title": "Updated Album"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["title"] == "Updated Album"
        finally:
            _clear_overrides()


class TestDeleteAlbum:
    @pytest.mark.anyio
    async def test_delete_album(self, client):
        """DELETE /albums/{id} → 204."""
        album_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.delete_album", new_callable=AsyncMock, return_value=True):
                resp = await client.delete(
                    f"/api/v1/albums/{album_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_album_not_found(self, client):
        """DELETE /albums/{id} → 404 when not found."""
        album_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.delete_album", new_callable=AsyncMock, return_value=False):
                resp = await client.delete(
                    f"/api/v1/albums/{album_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()


# ── Members ─────────────────────────────────────────────────────────────────


class TestAddMember:
    @pytest.mark.anyio
    async def test_add_member(self, client):
        """POST /albums/{id}/members → 201."""
        album_id = uuid.uuid4()
        target_user_id = str(uuid.uuid4())
        member = _make_member(album_id=album_id, user_id=target_user_id)
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.add_member", new_callable=AsyncMock, return_value=member):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/members?target_user_id={target_user_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
        finally:
            _clear_overrides()


class TestJoinAlbum:
    @pytest.mark.anyio
    async def test_join_album(self, client):
        """POST /albums/{id}/join → 201."""
        album_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.join_album",
                new_callable=AsyncMock,
                return_value={"id": str(uuid.uuid4()), "status": "PENDING"},
            ):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/join",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["status"] == "PENDING"
        finally:
            _clear_overrides()


class TestApproveMember:
    @pytest.mark.anyio
    async def test_approve_member(self, client):
        """PUT /albums/{id}/members/{member_id}/approve → 200."""
        album_id = uuid.uuid4()
        member_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.approve_member", new_callable=AsyncMock, return_value=True):
                resp = await client.put(
                    f"/api/v1/albums/{album_id}/members/{member_id}/approve",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["approved"] is True
        finally:
            _clear_overrides()


class TestRemoveMember:
    @pytest.mark.anyio
    async def test_remove_member(self, client):
        """DELETE /albums/{id}/members/{user_id} → 204."""
        album_id = uuid.uuid4()
        target_user_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.remove_member", new_callable=AsyncMock, return_value=True):
                resp = await client.delete(
                    f"/api/v1/albums/{album_id}/members/{target_user_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()


class TestListMembers:
    @pytest.mark.anyio
    async def test_list_members(self, client):
        """GET /albums/{id}/members → 200."""
        album_id = uuid.uuid4()
        member = _make_member(album_id=album_id)
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_members",
                new_callable=AsyncMock,
                return_value=([member], 1),
            ):
                resp = await client.get(
                    f"/api/v1/albums/{album_id}/members",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
        finally:
            _clear_overrides()


# ── Photos ──────────────────────────────────────────────────────────────────


class TestUploadPhoto:
    @pytest.mark.anyio
    async def test_upload_photo(self, client):
        """POST /albums/{id}/photos → 201."""
        album_id = uuid.uuid4()
        photo = _make_photo(album_id=album_id)
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.upload_photo", new_callable=AsyncMock, return_value=photo),
            ):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/photos",
                    files={
                        "file": ("photo.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100, "image/jpeg")
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["original_filename"] == "photo.jpg"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_photo_rate_limited(self, client):
        """POST /albums/{id}/photos → 429 when rate limited."""
        album_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/photos",
                    files={"file": ("photo.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_photo_invalid_type(self, client):
        """POST /albums/{id}/photos → 400 for invalid file type."""
        from app.core.errors import AppError, ErrorCode

        album_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.upload_photo",
                    new_callable=AsyncMock,
                    side_effect=AppError(ErrorCode.ALBUM_003, 400, "File type not allowed."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/photos",
                    files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_photo_quota_exceeded(self, client):
        """POST /albums/{id}/photos → 400 when storage quota exceeded."""
        from app.core.errors import AppError, ErrorCode

        album_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.upload_photo",
                    new_callable=AsyncMock,
                    side_effect=AppError(ErrorCode.ALBUM_002, 400, "Storage quota exceeded."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/photos",
                    files={"file": ("photo.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "quota" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()


class TestUploadFile:
    @pytest.mark.anyio
    async def test_upload_zip(self, client):
        """POST /albums/{id}/files → 201."""
        album_id = uuid.uuid4()
        photo = _make_photo(album_id=album_id)
        photo["is_zip"] = True
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.upload_file_zip", new_callable=AsyncMock, return_value=photo),
            ):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/files",
                    files={
                        "file": ("archive.zip", b"PK\x03\x04" + b"\x00" * 100, "application/zip")
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
        finally:
            _clear_overrides()


class TestListPhotos:
    @pytest.mark.anyio
    async def test_list_photos(self, client):
        """GET /albums/{id}/photos → 200."""
        album_id = uuid.uuid4()
        photo = _make_photo(album_id=album_id)
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_photos",
                new_callable=AsyncMock,
                return_value=([photo], 1),
            ):
                resp = await client.get(
                    f"/api/v1/albums/{album_id}/photos",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["photos"]) == 1
        finally:
            _clear_overrides()


class TestGetPhoto:
    @pytest.mark.anyio
    async def test_get_photo(self, client):
        """GET /albums/{id}/photos/{photo_id} → 200."""
        album_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        photo = _make_photo(photo_id=photo_id, album_id=album_id)
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.get_photo", new_callable=AsyncMock, return_value=photo):
                resp = await client.get(
                    f"/api/v1/albums/{album_id}/photos/{photo_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestUpdatePhoto:
    @pytest.mark.anyio
    async def test_update_photo_description(self, client):
        """PUT /albums/{id}/photos/{photo_id} → 200."""
        album_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        photo = _make_photo(photo_id=photo_id, album_id=album_id, user_id=user_id)
        photo["description"] = "Updated description"
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP}.update_photo", new_callable=AsyncMock, return_value=photo):
                resp = await client.put(
                    f"/api/v1/albums/{album_id}/photos/{photo_id}",
                    json={"description": "Updated description"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["description"] == "Updated description"
        finally:
            _clear_overrides()


class TestDeletePhoto:
    @pytest.mark.anyio
    async def test_delete_photo(self, client):
        """DELETE /albums/{id}/photos/{photo_id} → 204."""
        album_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.delete_photo", new_callable=AsyncMock, return_value=True):
                resp = await client.delete(
                    f"/api/v1/albums/{album_id}/photos/{photo_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_photo_not_found(self, client):
        """DELETE /albums/{id}/photos/{photo_id} → 404."""
        album_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.delete_photo", new_callable=AsyncMock, return_value=False):
                resp = await client.delete(
                    f"/api/v1/albums/{album_id}/photos/{photo_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_photo_permission_denied(self, client):
        """DELETE /albums/{id}/photos/{photo_id} → 403 for non-uploader."""
        from app.core.errors import AppError, ErrorCode

        album_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.delete_photo",
                new_callable=AsyncMock,
                side_effect=AppError(ErrorCode.SYS_403, 403, "Not authorized."),
            ):
                resp = await client.delete(
                    f"/api/v1/albums/{album_id}/photos/{photo_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


# ── Comments ────────────────────────────────────────────────────────────────


class TestCreateComment:
    @pytest.mark.anyio
    async def test_create_comment(self, client):
        """POST /albums/{id}/comments → 201."""
        album_id = uuid.uuid4()
        comment = _make_comment(album_id=album_id)
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.create_comment", new_callable=AsyncMock, return_value=comment),
            ):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/comments",
                    json={"content": "Nice photo!"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_comment_rate_limited(self, client):
        """POST /albums/{id}/comments → 429 when rate limited."""
        album_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/comments",
                    json={"content": "Nice photo!"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestListComments:
    @pytest.mark.anyio
    async def test_list_comments(self, client):
        """GET /albums/{id}/comments → 200."""
        album_id = uuid.uuid4()
        comment = _make_comment(album_id=album_id)
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_comments",
                new_callable=AsyncMock,
                return_value=([comment], 1),
            ):
                resp = await client.get(
                    f"/api/v1/albums/{album_id}/comments",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["comments"]) == 1
        finally:
            _clear_overrides()


class TestDeleteComment:
    @pytest.mark.anyio
    async def test_delete_comment(self, client):
        """DELETE /albums/{id}/comments/{comment_id} → 204."""
        album_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.delete_comment", new_callable=AsyncMock, return_value=True):
                resp = await client.delete(
                    f"/api/v1/albums/{album_id}/comments/{comment_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_comment_not_found(self, client):
        """DELETE /albums/{id}/comments/{comment_id} → 404."""
        album_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.delete_comment", new_callable=AsyncMock, return_value=False):
                resp = await client.delete(
                    f"/api/v1/albums/{album_id}/comments/{comment_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()


# ── Bug-fix regression tests ──────────────────────────────────────────────


class TestC1StatusEnum:
    """C1: Album status uses 'ACCEPTED' not 'APPROVED'."""

    @pytest.mark.anyio
    async def test_create_album_uses_accepted_status(self):
        """Service creates album member with 'ACCEPTED' status."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=_fake_album_row())
        mock_txn = AsyncMock()
        mock_txn.__aenter__ = AsyncMock(return_value=None)
        mock_txn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_txn)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = _FakeAcquire(mock_conn)

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.album_repo.insert_album",
                new_callable=AsyncMock,
                return_value=_fake_album_row(),
            ),
            patch(
                "app.repositories.album_repo.insert_member",
                new_callable=AsyncMock,
                return_value={"id": str(uuid.uuid4())},
            ) as mock_insert_member,
            patch(
                "app.repositories.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=_fake_album_row(),
            ),
        ):
            from app.services.album import create_album

            await create_album(title="Test", description=None, user_id=str(uuid.uuid4()))
            # Verify status="ACCEPTED" was passed (not "APPROVED")
            call_kwargs = mock_insert_member.call_args
            assert call_kwargs is not None
            # insert_member is called with positional args: conn, member_id, album_id, user_id, role=, status=
            assert call_kwargs.kwargs.get("status") == "ACCEPTED" or (
                len(call_kwargs.args) >= 6 and call_kwargs.args[5] == "ACCEPTED"
            )


class TestM5BlacklistAlbumListing:
    """M5: Blacklist filtering in album listing."""

    @pytest.mark.anyio
    async def test_list_albums_excludes_blocked_users(self):
        """list_albums passes blocked user IDs to repo."""
        blocked_uid = str(uuid.uuid4())
        viewer_uid = str(uuid.uuid4())
        album = _fake_album_row()

        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = _FakeAcquire(mock_conn)

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(f"{_SVC}.get_redis") as mock_get_redis,
            patch(
                f"{_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value={blocked_uid}
            ),
            patch(
                "app.repositories.album_repo.find_albums",
                new_callable=AsyncMock,
                return_value=([album], 1),
            ) as mock_find,
        ):
            mock_get_redis.return_value = MagicMock()
            from app.services.album import list_albums

            result, total = await list_albums(page=1, page_size=20, viewer_id=viewer_uid)
            assert total == 1
            # Verify exclude_user_ids was passed
            call_kwargs = mock_find.call_args
            exclude_ids = call_kwargs.kwargs.get("exclude_user_ids")
            assert exclude_ids is not None
            assert uuid.UUID(blocked_uid) in exclude_ids


class TestM5BlacklistPhotoListing:
    """M5: Blacklist filtering in photo listing."""

    @pytest.mark.anyio
    async def test_list_photos_excludes_blocked_users(self):
        """list_photos passes blocked user IDs to repo."""
        blocked_uid = str(uuid.uuid4())
        viewer_uid = str(uuid.uuid4())
        album_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        photo = {
            "id": uuid.uuid4(),
            "album_id": uuid.UUID(album_id),
            "uploaded_by": uuid.uuid4(),
            "uploaded_by_name": "Test User",
            "storage_key": "k",
            "thumbnail_key": None,
            "original_filename": "photo.jpg",
            "file_size_bytes": 1024,
            "content_type": "image/jpeg",
            "description": None,
            "width": None,
            "height": None,
            "is_zip": False,
            "created_at": now,
            "updated_at": now,
        }

        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = _FakeAcquire(mock_conn)

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(f"{_SVC}.get_redis") as mock_get_redis,
            patch(
                f"{_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value={blocked_uid}
            ),
            patch(
                "app.repositories.album_repo.find_photos",
                new_callable=AsyncMock,
                return_value=([photo], 1),
            ) as mock_find,
            patch(
                "app.converters.album_converter.generate_presigned_url",
                return_value="http://example.com/photo.jpg",
            ),
        ):
            mock_get_redis.return_value = MagicMock()
            from app.services.album import list_photos

            result, total = await list_photos(
                album_id=album_id, page=1, page_size=20, viewer_id=viewer_uid
            )
            assert total == 1
            call_kwargs = mock_find.call_args
            exclude_ids = call_kwargs.kwargs.get("exclude_user_ids")
            assert exclude_ids is not None
            assert uuid.UUID(blocked_uid) in exclude_ids


class TestM8StorageQuotaTransaction:
    """M8: Storage quota check uses FOR UPDATE in transaction."""

    @pytest.mark.anyio
    async def test_upload_photo_locks_quota_row(self):
        """upload_photo uses SELECT ... FOR UPDATE for storage quota."""
        user_uid = str(uuid.uuid4())
        user_uuid = uuid.UUID(user_uid)
        album_id = str(uuid.uuid4())
        album_uuid = uuid.UUID(album_id)

        fake_album = {
            "id": album_uuid,
            "title": "T",
            "description": None,
            "created_by": user_uuid,
            "is_deleted": False,
            "is_archived": False,
            "created_by_name": "X",
            "photo_count": 0,
            "member_count": 1,
        }
        fake_member = {"role": "MEMBER", "status": "ACCEPTED"}

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"storage_used_bytes": 0})
        mock_conn.execute = AsyncMock()

        mock_txn = AsyncMock()
        mock_txn.__aenter__ = AsyncMock(return_value=None)
        mock_txn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_txn)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = _FakeAcquire(mock_conn)

        photo_row = {
            "id": uuid.uuid4(),
            "album_id": album_uuid,
            "uploaded_by": user_uuid,
            "storage_key": "k",
            "original_filename": "photo.jpg",
            "file_size_bytes": 100,
            "content_type": "image/jpeg",
            "width": None,
            "height": None,
            "is_zip": False,
            "thumbnail_key": None,
            "description": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(f"{_SVC}.validate_magic_number", return_value=True),
            patch(
                "app.repositories.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=fake_album,
            ),
            patch(
                "app.repositories.album_repo.find_member",
                new_callable=AsyncMock,
                return_value=fake_member,
            ),
            patch(
                "app.repositories.album_repo.count_photos", new_callable=AsyncMock, return_value=0
            ),
            patch(
                "app.repositories.album_repo.insert_photo",
                new_callable=AsyncMock,
                return_value=photo_row,
            ),
            patch(
                "app.repositories.album_repo.find_photo_by_id",
                new_callable=AsyncMock,
                return_value={**photo_row, "uploaded_by_name": "X"},
            ),
            patch(f"{_SVC}.settings") as mock_settings,
        ):
            mock_settings.MAX_USER_STORAGE_BYTES = 1_000_000_000
            # Mock lazy imports in upload_photo
            with (
                patch("app.core.storage.album_photo_key", return_value="key"),
                patch("app.core.storage.album_thumbnail_key", return_value="thumb"),
                patch("app.core.storage.upload_file"),
            ):
                from app.services.album import upload_photo

                await upload_photo(
                    album_id=album_id,
                    user_id=user_uid,
                    file_data=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
                    filename="photo.jpg",
                    content_type="image/jpeg",
                )

            # Verify FOR UPDATE was used
            fetchrow_calls = mock_conn.fetchrow.call_args_list
            for_update_called = any(
                "FOR UPDATE" in str(call.args[0]) if call.args else False for call in fetchrow_calls
            )
            assert for_update_called, "Expected SELECT ... FOR UPDATE for storage quota check"


class TestM9UpdatePhotoSingleQuery:
    """M9: update_photo uses CTE — no redundant find_photo_by_id call."""

    @pytest.mark.anyio
    async def test_update_photo_no_redundant_fetch(self):
        """album_repo.update_photo uses CTE instead of separate find_photo_by_id."""
        photo_id = uuid.uuid4()
        mock_conn = AsyncMock()
        updated_row = {
            "id": photo_id,
            "album_id": uuid.uuid4(),
            "uploaded_by": uuid.uuid4(),
            "storage_key": "k",
            "original_filename": "photo.jpg",
            "file_size_bytes": 100,
            "content_type": "image/jpeg",
            "width": None,
            "height": None,
            "is_zip": False,
            "thumbnail_key": None,
            "description": "new desc",
            "uploaded_by_name": "Test User",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_conn.fetchrow = AsyncMock(
            return_value=MagicMock(
                **{
                    "__iter__": lambda s: iter(updated_row.items()),
                    "__getitem__": lambda s, k: updated_row[k],
                    "items": lambda: updated_row.items(),
                    "keys": lambda: updated_row.keys(),
                }
            )
        )

        from app.repositories.album_repo import update_photo

        result = await update_photo(mock_conn, photo_id, description="new desc")
        assert result is not None
        # Verify only ONE fetchrow call (the CTE), not two (update + find_photo_by_id)
        assert mock_conn.fetchrow.call_count == 1
        # Verify the query uses a CTE
        query = mock_conn.fetchrow.call_args.args[0]
        assert "WITH updated AS" in query


class TestL3ListCommentsAlbumNotFound:
    """L3: list_comments returns 404 for non-existent album."""

    @pytest.mark.anyio
    async def test_list_comments_album_not_found(self):
        """list_comments raises 404 when album doesn't exist."""
        from app.core.errors import AppError

        album_id = str(uuid.uuid4())

        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = _FakeAcquire(mock_conn)

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            from app.services.album import list_comments

            with pytest.raises(AppError) as exc_info:
                await list_comments(album_id=album_id, page=1, page_size=20)
            assert exc_info.value.status_code == 404


# ── Test helpers for service-layer mocks ───────────────────────────────────


def _fake_album_row(album_id=None, user_id=None):
    now = datetime.now(timezone.utc)
    uid = uuid.UUID(user_id) if user_id else uuid.uuid4()
    aid = album_id or uuid.uuid4()
    return {
        "id": aid,
        "title": "Test Album",
        "description": "A test album",
        "cover_photo_url": None,
        "created_by": uid,
        "created_by_name": "Test User",
        "is_deleted": False,
        "is_archived": False,
        "photo_count": 0,
        "member_count": 1,
        "created_at": now,
        "updated_at": now,
    }


class _FakeAcquire:
    """Async context manager that returns a mock connection."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass
