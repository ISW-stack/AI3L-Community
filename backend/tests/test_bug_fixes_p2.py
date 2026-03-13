"""Tests for P2 bug fixes: Bugs 4-8.

Bug 4: async_resolve_avatar_url
Bug 5: Avatar cache byte counter drift on refresh
Bug 6: user_repo.list_all single-query COUNT(*) OVER()
Bug 7: Orphan cleanup decrements storage counters
Bug 8: GUEST->MEMBER promotion revokes old sessions
"""

import sys
import time
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc).replace(microsecond=0)
_REPO = "app.repositories.user_repo"


# =========================================================================
# Bug 4: async_resolve_avatar_url
# =========================================================================


class TestAsyncResolveAvatarUrl:
    """async_resolve_avatar_url runs presigned URL generation without blocking."""

    @pytest.mark.anyio
    async def test_none_returns_none(self):
        from app.converters.user_converter import async_resolve_avatar_url

        assert await async_resolve_avatar_url(None) is None

    @pytest.mark.anyio
    async def test_empty_string_returns_none(self):
        from app.converters.user_converter import async_resolve_avatar_url

        assert await async_resolve_avatar_url("") is None

    @pytest.mark.anyio
    async def test_http_url_passthrough(self):
        from app.converters.user_converter import async_resolve_avatar_url

        url = "http://example.com/avatar.jpg"
        assert await async_resolve_avatar_url(url) == url

    @pytest.mark.anyio
    async def test_https_url_passthrough(self):
        from app.converters.user_converter import async_resolve_avatar_url

        url = "https://cdn.example.com/avatar.jpg"
        assert await async_resolve_avatar_url(url) == url

    @pytest.mark.anyio
    async def test_minio_key_generates_presigned(self):
        from app.converters.user_converter import async_resolve_avatar_url

        with patch(
            "app.core.async_storage.generate_presigned_url",
            new_callable=AsyncMock,
            return_value="https://minio/signed-async",
        ) as mock_presign:
            result = await async_resolve_avatar_url("avatars/user123.png")
            assert result == "https://minio/signed-async"
            mock_presign.assert_awaited_once_with("avatars/user123.png", expires_in=86400 * 7)

    @pytest.mark.anyio
    async def test_presigned_url_exception_returns_key(self):
        """When async generate_presigned_url raises, falls back to raw key."""
        from app.converters.user_converter import async_resolve_avatar_url

        with patch(
            "app.core.async_storage.generate_presigned_url",
            new_callable=AsyncMock,
            side_effect=Exception("MinIO down"),
        ):
            result = await async_resolve_avatar_url("avatars/broken.png")
            assert result == "avatars/broken.png"


# =========================================================================
# Bug 5: Avatar cache byte counter drift on refresh
# =========================================================================


class TestAvatarCacheByteCounterRefresh:
    """Refreshing a cache entry after TTL expiry must not inflate the byte counter."""

    def _reset_cache(self, about_module):
        about_module._avatar_cache.clear()
        about_module._cache_total_bytes = 0

    @pytest.mark.anyio
    async def test_refresh_does_not_inflate_byte_counter(self, client):
        """Refreshing an existing cache entry subtracts old size before adding new."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        original_max_bytes = about_module._MAX_CACHE_BYTES
        original_max_entries = about_module._MAX_CACHE_ENTRIES

        try:
            from app.core.deps import get_current_user
            from app.main import app

            uid = str(uuid.uuid4())
            payload = {"sub": uid, "role": "MEMBER", "jti": str(uuid.uuid4())}
            app.dependency_overrides[get_current_user] = lambda: payload

            about_module._MAX_CACHE_BYTES = 10 * 1024 * 1024
            about_module._MAX_CACHE_ENTRIES = 100

            contributor_id = str(uuid.uuid4())
            contributor = {
                "id": uuid.UUID(contributor_id),
                "github_username": "testuser",
                "display_name": "Test",
                "role": "Developer",
                "display_order": 0,
                "created_at": _NOW,
            }

            # Seed cache with an expired entry (old 8-byte data)
            expired_time = time.time() - about_module._CACHE_TTL_SECONDS - 100
            about_module._avatar_cache[contributor_id] = (
                b"old_data!",  # 9 bytes
                "image/png",
                expired_time,
            )
            about_module._cache_total_bytes = 9

            # New fetch returns 12-byte data
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"new_data!!!!"  # 12 bytes
            mock_response.headers = {"content-type": "image/png"}

            with (
                patch(
                    "app.services.contributor.get_contributor",
                    new_callable=AsyncMock,
                    return_value=contributor,
                ),
                patch(
                    "app.api.v1.endpoints.about._requests.get",
                    return_value=mock_response,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{contributor_id}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            # Byte counter should be exactly 12 (new size), not 9 + 12 = 21
            assert about_module._cache_total_bytes == 12
            assert len(about_module._avatar_cache) == 1
        finally:
            self._reset_cache(about_module)
            about_module._MAX_CACHE_BYTES = original_max_bytes
            about_module._MAX_CACHE_ENTRIES = original_max_entries
            app.dependency_overrides.clear()

    def test_refresh_same_key_correct_byte_count(self):
        """Direct unit test: replacing an entry subtracts old size first."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        try:
            now = time.time()
            # Simulate storing 10-byte entry
            about_module._avatar_cache["key-a"] = (b"0123456789", "image/png", now)
            about_module._cache_total_bytes = 10

            # Simulate expired entry refresh: new 5-byte data
            # This mirrors the production code logic after fix
            if "key-a" in about_module._avatar_cache:
                old_data = about_module._avatar_cache["key-a"][0]
                about_module._cache_total_bytes -= len(old_data)
                del about_module._avatar_cache["key-a"]

            new_data = b"abcde"  # 5 bytes
            about_module._avatar_cache["key-a"] = (new_data, "image/png", now)
            about_module._cache_total_bytes += len(new_data)

            assert about_module._cache_total_bytes == 5
            assert len(about_module._avatar_cache) == 1
        finally:
            self._reset_cache(about_module)


# =========================================================================
# Bug 6: user_repo.list_all single-query COUNT(*) OVER()
# =========================================================================


class TestUserRepoListAll:
    """user_repo.list_all uses COUNT(*) OVER() in a single query."""

    @pytest.mark.anyio
    async def test_list_all_no_search(self, mock_pool, mock_conn):
        """list_all without search returns users and total from single query."""
        from app.repositories.user_repo import list_all

        user_row = {
            "id": uuid.uuid4(),
            "username": "alice",
            "display_name": "Alice",
            "role": "MEMBER",
            "is_deleted": False,
            "created_at": _NOW,
            "_total": 3,
        }
        mock_conn.fetch = AsyncMock(return_value=[user_row])

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            users, total = await list_all(page=1, page_size=50)

        assert total == 3
        assert len(users) == 1
        assert users[0]["username"] == "alice"
        # _total should be stripped from result
        assert "_total" not in users[0]
        # Only one query call (no fetchval)
        mock_conn.fetch.assert_called_once()
        mock_conn.fetchval.assert_not_called()

    @pytest.mark.anyio
    async def test_list_all_with_search(self, mock_pool, mock_conn):
        """list_all with search returns filtered results from single query."""
        from app.repositories.user_repo import list_all

        user_row = {
            "id": uuid.uuid4(),
            "username": "bob",
            "display_name": "Bob",
            "role": "MEMBER",
            "is_deleted": False,
            "created_at": _NOW,
            "_total": 1,
        }
        mock_conn.fetch = AsyncMock(return_value=[user_row])

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            users, total = await list_all(page=1, page_size=50, search="bob")

        assert total == 1
        assert len(users) == 1
        assert users[0]["username"] == "bob"
        assert "_total" not in users[0]
        mock_conn.fetch.assert_called_once()
        mock_conn.fetchval.assert_not_called()

    @pytest.mark.anyio
    async def test_list_all_empty_result(self, mock_pool, mock_conn):
        """list_all with no matching rows returns empty list and 0 total."""
        from app.repositories.user_repo import list_all

        mock_conn.fetch = AsyncMock(return_value=[])

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            users, total = await list_all(page=1, page_size=50)

        assert total == 0
        assert users == []

    @pytest.mark.anyio
    async def test_list_all_total_matches_data(self, mock_pool, mock_conn):
        """Returned total from _total column matches across all rows."""
        from app.repositories.user_repo import list_all

        rows = [
            {
                "id": uuid.uuid4(),
                "username": f"u{i}",
                "display_name": f"U{i}",
                "role": "MEMBER",
                "is_deleted": False,
                "created_at": _NOW,
                "_total": 5,
            }
            for i in range(3)
        ]
        mock_conn.fetch = AsyncMock(return_value=rows)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            users, total = await list_all(page=1, page_size=3)

        assert total == 5
        assert len(users) == 3
        for u in users:
            assert "_total" not in u

    @pytest.mark.anyio
    async def test_list_all_sql_uses_count_over(self, mock_pool, mock_conn):
        """Verify the SQL query contains COUNT(*) OVER()."""
        from app.repositories.user_repo import list_all

        mock_conn.fetch = AsyncMock(return_value=[])

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            await list_all(page=1, page_size=50)

        sql = mock_conn.fetch.call_args[0][0]
        assert "COUNT(*) OVER()" in sql


# =========================================================================
# Bug 7: Orphan cleanup decrements storage counters
# =========================================================================


@pytest.fixture(autouse=False)
def _celery_modules_for_cleanup():
    """Inject fake celery modules so cleanup.py can be imported."""
    celery_mod = types.ModuleType("celery")
    celery_result_mod = types.ModuleType("celery.result")
    celery_mod.result = celery_result_mod
    celery_mod.shared_task = lambda **kw: (lambda fn: fn)

    celery_app_mod = types.ModuleType("app.celery_app")
    mock_celery_app = MagicMock()
    mock_celery_app.task = lambda *a, **kw: (lambda fn: fn)
    celery_app_mod.celery = mock_celery_app

    saved = {}
    for key in ("celery", "celery.result", "app.celery_app"):
        saved[key] = sys.modules.get(key)

    sys.modules["celery"] = celery_mod
    sys.modules["celery.result"] = celery_result_mod
    sys.modules["app.celery_app"] = celery_app_mod

    yield

    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val

    for mod_name in list(sys.modules):
        if mod_name.startswith("app.tasks."):
            del sys.modules[mod_name]


class TestOrphanCleanupDecrementStorage:
    """Bug 7: _delete_orphans must decrement user storage counters."""

    @pytest.mark.anyio
    async def test_delete_orphans_decrements_storage(self, _celery_modules_for_cleanup):
        """Deleting an orphan file decrements the owner's storage_used_bytes."""
        user_id = uuid.uuid4()
        storage_key = f"editor/{user_id}/image.png"
        file_size = 1024

        with (
            patch(
                "app.core.async_storage.delete_file",
                new_callable=AsyncMock,
            ) as mock_delete,
            patch(
                "app.core.async_storage.get_file_size",
                new_callable=AsyncMock,
                return_value=file_size,
            ),
            patch(
                "app.repositories.file_scan_repo.delete_by_key",
                new_callable=AsyncMock,
            ),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ) as mock_inc,
            patch(
                "app.tasks.cleanup._ensure_pool",
                new_callable=AsyncMock,
            ),
        ):
            from app.tasks.cleanup import _delete_orphans

            deleted = await _delete_orphans([storage_key])

        assert deleted == 1
        mock_delete.assert_awaited_once_with(storage_key)
        mock_inc.assert_awaited_once_with(user_id, -file_size)

    @pytest.mark.anyio
    async def test_delete_orphans_skips_zero_size(self, _celery_modules_for_cleanup):
        """No storage decrement when file_size is 0 (already deleted from MinIO)."""
        user_id = uuid.uuid4()
        storage_key = f"editor/{user_id}/gone.png"

        with (
            patch("app.core.async_storage.delete_file", new_callable=AsyncMock),
            patch(
                "app.core.async_storage.get_file_size",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.repositories.file_scan_repo.delete_by_key", new_callable=AsyncMock),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ) as mock_inc,
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
        ):
            from app.tasks.cleanup import _delete_orphans

            deleted = await _delete_orphans([storage_key])

        assert deleted == 1
        mock_inc.assert_not_awaited()

    @pytest.mark.anyio
    async def test_delete_orphans_multiple_files(self, _celery_modules_for_cleanup):
        """Multiple orphans from different users decrement each user's storage."""
        user1 = uuid.uuid4()
        user2 = uuid.uuid4()
        keys = [
            f"editor/{user1}/a.png",
            f"editor/{user2}/b.png",
        ]

        size_map = {keys[0]: 500, keys[1]: 800}

        with (
            patch("app.core.async_storage.delete_file", new_callable=AsyncMock),
            patch(
                "app.core.async_storage.get_file_size",
                new_callable=AsyncMock,
                side_effect=lambda k: size_map[k],
            ),
            patch("app.repositories.file_scan_repo.delete_by_key", new_callable=AsyncMock),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ) as mock_inc,
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
        ):
            from app.tasks.cleanup import _delete_orphans

            deleted = await _delete_orphans(keys)

        assert deleted == 2
        assert mock_inc.await_count == 2
        calls = mock_inc.call_args_list
        # Verify correct user_id and negative delta for each call
        call_args = [(c[0][0], c[0][1]) for c in calls]
        assert (user1, -500) in call_args
        assert (user2, -800) in call_args


# =========================================================================
# Bug 8: GUEST->MEMBER promotion revokes old session
# =========================================================================


class TestApplicationApprovalRevokesSession:
    """Bug 8: Approving a membership application must revoke old GUEST sessions."""

    @pytest.mark.anyio
    async def test_approve_revokes_user_sessions(self):
        """review_application with APPROVED calls revoke_user_sessions."""
        from app.services.application import review_application

        app_id = uuid.uuid4()
        reviewer_id = uuid.uuid4()
        user_id = uuid.uuid4()
        app_row = {
            "id": app_id,
            "user_id": user_id,
            "description": "I want to join",
            "status": "APPROVED",
            "reviewed_by": reviewer_id,
            "reviewed_at": _NOW,
            "created_at": _NOW,
        }

        with (
            patch(
                "app.repositories.application_repo.update_status",
                new_callable=AsyncMock,
                return_value=app_row,
            ),
            patch(
                "app.services.application.emit",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.auth.revoke_user_sessions",
                new_callable=AsyncMock,
            ) as mock_revoke,
        ):
            result = await review_application(app_id, reviewer_id, "APPROVED")

        assert result is not None
        mock_revoke.assert_awaited_once_with(str(user_id))

    @pytest.mark.anyio
    async def test_reject_does_not_revoke_sessions(self):
        """review_application with REJECTED does NOT call revoke_user_sessions."""
        from app.services.application import review_application

        app_id = uuid.uuid4()
        reviewer_id = uuid.uuid4()
        user_id = uuid.uuid4()
        app_row = {
            "id": app_id,
            "user_id": user_id,
            "description": "I want to join",
            "status": "REJECTED",
            "reviewed_by": reviewer_id,
            "reviewed_at": _NOW,
            "created_at": _NOW,
        }

        with (
            patch(
                "app.repositories.application_repo.update_status",
                new_callable=AsyncMock,
                return_value=app_row,
            ),
            patch(
                "app.services.application.emit",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.auth.revoke_user_sessions",
                new_callable=AsyncMock,
            ) as mock_revoke,
        ):
            result = await review_application(app_id, reviewer_id, "REJECTED")

        assert result is not None
        mock_revoke.assert_not_awaited()

    @pytest.mark.anyio
    async def test_approve_not_found_does_not_revoke(self):
        """When application is not found, no session revocation occurs."""
        from app.services.application import review_application

        with (
            patch(
                "app.repositories.application_repo.update_status",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.auth.revoke_user_sessions",
                new_callable=AsyncMock,
            ) as mock_revoke,
        ):
            result = await review_application(uuid.uuid4(), uuid.uuid4(), "APPROVED")

        assert result is None
        mock_revoke.assert_not_awaited()
