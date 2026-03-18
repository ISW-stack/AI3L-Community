"""Tests for system bug fixes B02, B03, B04, B08.

B02: Album upload reads file in chunks with size limit.
B03: Files with "pending" scan status are blocked from serving.
B04: register_new_user re-verifies invite code expiry in UPDATE.
B08: update_post rejects empty content after sanitization.
"""

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EP_ALBUMS = "app.api.v1.endpoints.albums"
_EP_FILES = "app.api.v1.endpoints.files"
_EP_POSTS = "app.api.v1.endpoints.posts"
_SVC_AUTH = "app.services.auth"


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


def _make_photo(album_id=None):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "album_id": str(album_id or uuid.uuid4()),
        "uploaded_by": str(uuid.uuid4()),
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


def _make_post(post_id=None, user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(post_id or uuid.uuid4()),
        "title": "Test Post",
        "content": "<p>Body</p>",
        "author": {
            "id": uid,
            "username": "testuser",
            "display_name": "Test User",
            "avatar_url": None,
        },
        "category_id": None,
        "category_name": None,
        "keywords": ["test"],
        "allow_comments": True,
        "version": 1,
        "comment_count": 0,
        "created_at": now,
        "updated_at": now,
    }


# ── B02: Album endpoint chunked upload with size limit ─────────────────────


class TestB02AlbumUploadSizeLimit:
    """B02: upload_photo_endpoint and upload_file_endpoint reject oversized files."""

    @pytest.mark.anyio
    async def test_upload_photo_oversized_rejected(self, client):
        """POST /albums/{id}/photos with >50MB file → 413."""
        album_id = uuid.uuid4()
        # Use a moderately oversized file (just over the limit) to avoid
        # memory issues in tests. Use 51MB which is over the 50MB limit.
        oversized_data = b"\xff\xd8\xff\xe0" + b"\x00" * (50 * 1024 * 1024 + 100)
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_ALBUMS}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/photos",
                    files={
                        "file": ("big.jpg", io.BytesIO(oversized_data), "image/jpeg")
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 413
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_file_oversized_rejected(self, client):
        """POST /albums/{id}/files with >50MB file → 413."""
        album_id = uuid.uuid4()
        oversized_data = b"PK\x03\x04" + b"\x00" * (50 * 1024 * 1024 + 100)
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_ALBUMS}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/files",
                    files={
                        "file": (
                            "big.zip",
                            io.BytesIO(oversized_data),
                            "application/zip",
                        )
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 413
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_photo_under_limit_passes(self, client):
        """POST /albums/{id}/photos with small file → 201 (passes size check)."""
        album_id = uuid.uuid4()
        photo = _make_photo(album_id=album_id)
        small_data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP_ALBUMS}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_EP_ALBUMS}.upload_photo",
                    new_callable=AsyncMock,
                    return_value=photo,
                ),
            ):
                resp = await client.post(
                    f"/api/v1/albums/{album_id}/photos",
                    files={
                        "file": ("small.jpg", io.BytesIO(small_data), "image/jpeg")
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_chunked_read_constant_exists(self):
        """Verify MAX_ALBUM_UPLOAD_BYTES constant is defined correctly."""
        from app.core.constants import MAX_ALBUM_UPLOAD_BYTES

        assert MAX_ALBUM_UPLOAD_BYTES == 50 * 1024 * 1024


# ── B03: Pending scan status blocks file serving ───────────────────────────


class TestB03PendingScanBlocked:
    """B03: serve_file blocks files with 'pending' scan status."""

    @pytest.mark.anyio
    async def test_serve_file_pending_returns_202(self, client):
        """GET /files/content/{key} with pending scan → 202."""
        key = "editor/user123/abc123.png"
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_FILES}.file_scan_repo.find_by_key",
                new_callable=AsyncMock,
                return_value={"status": "pending", "positives": None, "total": None},
            ):
                resp = await client.get(
                    f"/api/v1/files/content/{key}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 202
                assert "being scanned" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_serve_file_malicious_returns_451(self, client):
        """GET /files/content/{key} with malicious scan → 451 (unchanged behavior)."""
        key = "editor/user123/abc123.png"
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_FILES}.file_scan_repo.find_by_key",
                new_callable=AsyncMock,
                return_value={"status": "malicious", "positives": 5, "total": 70},
            ):
                resp = await client.get(
                    f"/api/v1/files/content/{key}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 451
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_serve_file_clean_passes(self, client):
        """GET /files/content/{key} with clean scan → 200 (file served)."""
        key = "editor/user123/abc123.png"
        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP_FILES}.file_scan_repo.find_by_key",
                    new_callable=AsyncMock,
                    return_value={"status": "clean", "positives": 0, "total": 70},
                ),
                patch(
                    f"{_EP_FILES}.async_download_file",
                    new_callable=AsyncMock,
                    return_value=(b"PNG data", "image/png"),
                ),
            ):
                resp = await client.get(
                    f"/api/v1/files/content/{key}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_serve_file_no_scan_record_passes(self, client):
        """GET /files/content/{key} with no scan record → 200 (file served)."""
        key = "editor/user123/abc123.png"
        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP_FILES}.file_scan_repo.find_by_key",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
                patch(
                    f"{_EP_FILES}.async_download_file",
                    new_callable=AsyncMock,
                    return_value=(b"PNG data", "image/png"),
                ),
            ):
                resp = await client.get(
                    f"/api/v1/files/content/{key}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


# ── B04: register_new_user re-verifies invite code expiry ──────────────────


class TestB04InviteCodeExpiryRecheck:
    """B04: register_new_user adds expires_at > NOW() to UPDATE WHERE clause."""

    @pytest.mark.anyio
    async def test_expired_invite_code_rejected_during_registration(self):
        """Expired invite code (not consumed) fails in register_new_user."""
        mock_conn = AsyncMock()
        mock_txn = AsyncMock()
        mock_txn.__aenter__ = AsyncMock(return_value=None)
        mock_txn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_txn)

        # INSERT user succeeds
        now = datetime.now(timezone.utc)
        user_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "id": user_id,
                "username": "newuser",
                "password_hash": "hash",
                "role": "MEMBER",
                "display_name": "newuser",
                "avatar_url": None,
                "orcid": None,
                "affiliation": None,
                "bio": None,
                "is_deleted": False,
                "is_banned": False,
                "ban_reason": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        # UPDATE invite_codes returns "UPDATE 0" (expired code not matched)
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = _FakeAcquire(mock_conn)

        with (
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                "app.core.security.async_hash_password",
                new_callable=AsyncMock,
                return_value="hashed",
            ),
        ):
            from app.services.auth import register_new_user

            with pytest.raises(ValueError, match="consumed or expired"):
                await register_new_user(
                    username="newuser",
                    password="Password1!",
                    display_name="New User",
                    invite_code="EXPIRED-CODE",
                )

    @pytest.mark.anyio
    async def test_update_query_includes_expires_at_check(self):
        """The UPDATE query includes 'expires_at > NOW()' in the WHERE clause."""
        mock_conn = AsyncMock()
        mock_txn = AsyncMock()
        mock_txn.__aenter__ = AsyncMock(return_value=None)
        mock_txn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_txn)

        now = datetime.now(timezone.utc)
        user_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "id": user_id,
                "username": "newuser",
                "password_hash": "hash",
                "role": "MEMBER",
                "display_name": "newuser",
                "avatar_url": None,
                "orcid": None,
                "affiliation": None,
                "bio": None,
                "is_deleted": False,
                "is_banned": False,
                "ban_reason": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        # Succeed to verify the query structure
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = _FakeAcquire(mock_conn)

        with (
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                "app.core.security.async_hash_password",
                new_callable=AsyncMock,
                return_value="hashed",
            ),
        ):
            from app.services.auth import register_new_user

            await register_new_user(
                username="newuser",
                password="Password1!",
                display_name="New User",
                invite_code="VALID-CODE",
            )

            # Verify the execute call includes expires_at > NOW()
            execute_calls = mock_conn.execute.call_args_list
            update_call = [
                c for c in execute_calls if "invite_codes" in str(c.args[0])
            ]
            assert len(update_call) == 1
            query = update_call[0].args[0]
            assert "expires_at > NOW()" in query
            assert "consumed_at IS NULL" in query


# ── B08: update_post rejects empty content after sanitization ──────────────


class TestB08EmptyContentAfterSanitization:
    """B08: update_post endpoint rejects content that becomes empty after sanitization."""

    @pytest.mark.anyio
    async def test_update_post_empty_after_sanitize_returns_400(self, client):
        """PUT /posts/{id} with content that sanitizes to empty → 400."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(
                    f"{_EP_POSTS}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_EP_POSTS}.sanitize_html",
                    return_value="",
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={
                        "content": "<script>alert('xss')</script>",
                        "version": 1,
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert (
                    "empty after sanitization"
                    in resp.json()["detail"]["message"].lower()
                )
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_post_whitespace_after_sanitize_returns_400(self, client):
        """PUT /posts/{id} with content that sanitizes to whitespace → 400."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(
                    f"{_EP_POSTS}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_EP_POSTS}.sanitize_html",
                    return_value="   \n  ",
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={
                        "content": "<div>   </div>",
                        "version": 1,
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert (
                    "empty after sanitization"
                    in resp.json()["detail"]["message"].lower()
                )
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_post_valid_content_passes(self, client):
        """PUT /posts/{id} with valid content after sanitization → 200."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        post = _make_post(post_id=post_id, user_id=user_id)
        post["content"] = "<p>Updated content</p>"
        post["version"] = 2

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(
                    f"{_EP_POSTS}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_EP_POSTS}.sanitize_html",
                    return_value="<p>Updated content</p>",
                ),
                patch(
                    f"{_EP_POSTS}.update_post",
                    new_callable=AsyncMock,
                    return_value=post,
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={
                        "content": "<p>Updated content</p>",
                        "version": 1,
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_post_null_content_passes(self, client):
        """PUT /posts/{id} with no content field (only title) → 200."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        post = _make_post(post_id=post_id, user_id=user_id)
        post["title"] = "New Title"
        post["version"] = 2

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(
                    f"{_EP_POSTS}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_EP_POSTS}.update_post",
                    new_callable=AsyncMock,
                    return_value=post,
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={
                        "title": "New Title",
                        "version": 1,
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


# ── Helper ─────────────────────────────────────────────────────────────────


class _FakeAcquire:
    """Async context manager that returns a mock connection."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass
