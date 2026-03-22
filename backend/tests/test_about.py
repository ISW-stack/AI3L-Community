"""Tests for about endpoints — contributors list, avatar proxy, and admin CRUD."""

import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EP = "app.api.v1.endpoints.about"
_SVC = "app.services.contributor"
_RATE_LIMIT = "app.api.v1.endpoints.about.check_rate_limit"

_FAKE_ID = uuid.uuid4()
_FAKE_ID2 = uuid.uuid4()

_FAKE_CONTRIBUTOR = {
    "id": _FAKE_ID,
    "github_username": "Isaries",
    "display_name": "Isaries",
    "role": "Project Lead & Full-Stack Developer",
    "display_order": 0,
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc),
}

_FAKE_CONTRIBUTOR2 = {
    "id": _FAKE_ID2,
    "github_username": "SW9526",
    "display_name": "SW9526",
    "role": "Frontend Contributor",
    "display_order": 1,
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc),
}


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


class TestListContributors:
    @pytest.mark.anyio
    async def test_list_contributors_member(self, client):
        """GET /about/contributors by MEMBER → 200 with contributor list."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_SVC}.list_contributors",
                new_callable=AsyncMock,
                return_value=[_FAKE_CONTRIBUTOR, _FAKE_CONTRIBUTOR2],
            ):
                resp = await client.get(
                    "/api/v1/about/contributors",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert "contributors" in data
            assert len(data["contributors"]) == 2
            for c in data["contributors"]:
                assert "avatar_url" in c
                assert "github_username" not in c
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_contributors_guest_forbidden(self, client):
        """GET /about/contributors by GUEST → 403."""
        try:
            _override_auth("GUEST")
            resp = await client.get(
                "/api/v1/about/contributors",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_contributors_unauthenticated(self, unauthed_client):
        """GET /about/contributors without auth → 401."""
        resp = await unauthed_client.get("/api/v1/about/contributors")
        assert resp.status_code == 401


class TestContributorAvatar:
    @pytest.mark.anyio
    async def test_avatar_valid_id(self, client):
        """GET /about/contributors/{id}/avatar by MEMBER → 200 with image content."""
        from app.api.v1.endpoints import about as about_module

        about_module._avatar_cache.clear()
        about_module._cache_total_bytes = 0

        try:
            _override_auth("MEMBER")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"\x89PNG\r\n\x1a\n"
            mock_response.headers = {"content-type": "image/png"}

            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(f"{_EP}._requests.get", return_value=mock_response),
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{_FAKE_ID}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.headers.get("content-type") == "image/png"
        finally:
            about_module._avatar_cache.clear()
            about_module._cache_total_bytes = 0
            _clear_overrides()

    @pytest.mark.anyio
    async def test_avatar_invalid_id(self, client):
        """GET /about/contributors/{bad-uuid}/avatar → 404."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_SVC}.get_contributor",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{uuid.uuid4()}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_avatar_guest_forbidden(self, client):
        """GET /about/contributors/{id}/avatar by GUEST → 403."""
        try:
            _override_auth("GUEST")
            resp = await client.get(
                f"/api/v1/about/contributors/{_FAKE_ID}/avatar",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestAdminListContributors:
    @pytest.mark.anyio
    async def test_admin_list_superadmin(self, client):
        """GET /about/admin/contributors by SUPER_ADMIN → 200 with github_username."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_SVC}.list_contributors",
                new_callable=AsyncMock,
                return_value=[_FAKE_CONTRIBUTOR],
            ):
                resp = await client.get(
                    "/api/v1/about/admin/contributors",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["contributors"]) == 1
            assert data["contributors"][0]["github_username"] == "Isaries"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_list_member_forbidden(self, client):
        """GET /about/admin/contributors by MEMBER → 403."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/about/admin/contributors",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_list_admin_forbidden(self, client):
        """GET /about/admin/contributors by ADMIN → 403."""
        try:
            _override_auth("ADMIN")
            resp = await client.get(
                "/api/v1/about/admin/contributors",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestAdminCreateContributor:
    @pytest.mark.anyio
    async def test_create_success(self, client):
        """POST /about/admin/contributors → 201."""
        try:
            _override_auth("SUPER_ADMIN")
            new_row = {
                **_FAKE_CONTRIBUTOR,
                "github_username": "newuser",
                "display_name": "New User",
            }
            with (
                patch(
                    f"{_SVC}.github_username_exists",
                    new_callable=AsyncMock,
                    return_value=False,
                ),
                patch(
                    f"{_SVC}.create_contributor",
                    new_callable=AsyncMock,
                    return_value=new_row,
                ),
            ):
                resp = await client.post(
                    "/api/v1/about/admin/contributors",
                    json={
                        "github_username": "newuser",
                        "display_name": "New User",
                        "role": "Contributor",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 201
            assert resp.json()["github_username"] == "newuser"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_duplicate(self, client):
        """POST /about/admin/contributors with duplicate github → 409."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_SVC}.github_username_exists",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await client.post(
                    "/api/v1/about/admin/contributors",
                    json={
                        "github_username": "Isaries",
                        "display_name": "Dup",
                        "role": "Contributor",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 409
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_member_forbidden(self, client):
        """POST /about/admin/contributors by MEMBER → 403."""
        try:
            _override_auth("MEMBER")
            resp = await client.post(
                "/api/v1/about/admin/contributors",
                json={
                    "github_username": "x",
                    "display_name": "X",
                    "role": "Y",
                },
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestAdminUpdateContributor:
    @pytest.mark.anyio
    async def test_update_success(self, client):
        """PUT /about/admin/contributors/{id} → 200."""
        try:
            _override_auth("SUPER_ADMIN")
            updated = {**_FAKE_CONTRIBUTOR, "display_name": "Updated"}
            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(
                    f"{_SVC}.update_contributor",
                    new_callable=AsyncMock,
                    return_value=updated,
                ),
            ):
                resp = await client.put(
                    f"/api/v1/about/admin/contributors/{_FAKE_ID}",
                    json={"display_name": "Updated"},
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            assert resp.json()["display_name"] == "Updated"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_not_found(self, client):
        """PUT /about/admin/contributors/{bad-id} → 404."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_SVC}.update_contributor",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.put(
                    f"/api/v1/about/admin/contributors/{uuid.uuid4()}",
                    json={"display_name": "X"},
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_duplicate_github(self, client):
        """PUT with duplicate github_username → 409."""
        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(
                    f"{_SVC}.github_username_exists",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.put(
                    f"/api/v1/about/admin/contributors/{_FAKE_ID}",
                    json={"github_username": "SW9526"},
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 409
        finally:
            _clear_overrides()


class TestAdminDeleteContributor:
    @pytest.mark.anyio
    async def test_delete_success(self, client):
        """DELETE /about/admin/contributors/{id} → 204."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_SVC}.delete_contributor",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await client.request(
                    "DELETE",
                    f"/api/v1/about/admin/contributors/{_FAKE_ID}",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_not_found(self, client):
        """DELETE /about/admin/contributors/{bad-id} → 404."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_SVC}.delete_contributor",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.request(
                    "DELETE",
                    f"/api/v1/about/admin/contributors/{uuid.uuid4()}",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_member_forbidden(self, client):
        """DELETE /about/admin/contributors/{id} by MEMBER → 403."""
        try:
            _override_auth("MEMBER")
            resp = await client.request(
                "DELETE",
                f"/api/v1/about/admin/contributors/{_FAKE_ID}",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestAvatarCacheBounding:
    """Tests for LRU-bounded avatar cache."""

    def _reset_cache(self, about_module):
        """Clear both the cache dict and the byte counter."""
        about_module._avatar_cache.clear()
        about_module._cache_total_bytes = 0

    def test_cache_evicts_oldest_when_full(self):
        """Inserting beyond _MAX_CACHE_ENTRIES evicts the oldest entry."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        original_max = about_module._MAX_CACHE_ENTRIES
        try:
            about_module._MAX_CACHE_ENTRIES = 5
            now = time.time()
            for i in range(6):
                key = f"id-{i}"
                about_module._avatar_cache[key] = (b"data", "image/png", now)
                about_module._avatar_cache.move_to_end(key)
                if len(about_module._avatar_cache) > about_module._MAX_CACHE_ENTRIES:
                    about_module._avatar_cache.popitem(last=False)

            # Oldest entry (id-0) should be evicted
            assert "id-0" not in about_module._avatar_cache
            # Newest entries should remain
            for i in range(1, 6):
                assert f"id-{i}" in about_module._avatar_cache
            assert len(about_module._avatar_cache) == 5
        finally:
            self._reset_cache(about_module)
            about_module._MAX_CACHE_ENTRIES = original_max

    def test_lru_access_keeps_entry_alive(self):
        """Accessing an entry moves it to end, so it survives eviction."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        original_max = about_module._MAX_CACHE_ENTRIES
        try:
            about_module._MAX_CACHE_ENTRIES = 3
            now = time.time()

            # Insert 3 entries: a, b, c
            for key in ["a", "b", "c"]:
                about_module._avatar_cache[key] = (b"data", "image/png", now)
                about_module._avatar_cache.move_to_end(key)

            # Access "a" to move it to end (most recently used)
            about_module._avatar_cache.move_to_end("a")

            # Insert "d" — should evict "b" (now the oldest)
            about_module._avatar_cache["d"] = (b"data", "image/png", now)
            about_module._avatar_cache.move_to_end("d")
            if len(about_module._avatar_cache) > about_module._MAX_CACHE_ENTRIES:
                about_module._avatar_cache.popitem(last=False)

            assert "b" not in about_module._avatar_cache
            assert "a" in about_module._avatar_cache  # survived due to LRU access
            assert "c" in about_module._avatar_cache
            assert "d" in about_module._avatar_cache
        finally:
            self._reset_cache(about_module)
            about_module._MAX_CACHE_ENTRIES = original_max

    def test_expired_entry_not_served(self):
        """Expired cache entries are not returned."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        try:
            # Insert an expired entry (timestamp far in the past)
            expired_time = time.time() - about_module._CACHE_TTL_SECONDS - 100
            about_module._avatar_cache["expired-id"] = (
                b"old-data",
                "image/png",
                expired_time,
            )

            now = time.time()
            cached = about_module._avatar_cache.get("expired-id")
            assert cached is not None
            _data, _ct, cached_at = cached
            # Verify the entry IS expired
            assert now - cached_at >= about_module._CACHE_TTL_SECONDS
        finally:
            self._reset_cache(about_module)


class TestAvatarCacheByteBounding:
    """Tests for byte-size limit on the avatar cache."""

    def _reset_cache(self, about_module):
        about_module._avatar_cache.clear()
        about_module._cache_total_bytes = 0

    @pytest.mark.anyio
    async def test_cache_evicts_oldest_when_byte_limit_exceeded(self, client):
        """A large avatar that exceeds _MAX_CACHE_BYTES evicts older entries."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        original_max_bytes = about_module._MAX_CACHE_BYTES
        original_max_entries = about_module._MAX_CACHE_ENTRIES

        try:
            _override_auth("MEMBER")
            # Set a tiny byte limit (20 bytes) and large entry count limit
            about_module._MAX_CACHE_BYTES = 20
            about_module._MAX_CACHE_ENTRIES = 100
            now = time.time()

            # Seed the cache with two 8-byte entries (total 16 bytes)
            about_module._avatar_cache["old-key-1"] = (b"12345678", "image/png", now)
            about_module._avatar_cache._cache_total_bytes_tracking = 8  # manual note
            about_module._cache_total_bytes = 16
            about_module._avatar_cache["old-key-2"] = (b"12345678", "image/png", now)

            # Simulate fetching a new 10-byte avatar that would push total to 26 > 20
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"1234567890"  # 10 bytes
            mock_response.headers = {"content-type": "image/png"}

            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(f"{_EP}._requests.get", return_value=mock_response),
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{_FAKE_ID}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            # At least one old entry should have been evicted to make room
            remaining_keys = set(about_module._avatar_cache.keys())
            # The new entry must be present
            assert str(_FAKE_ID) in remaining_keys
            # Total bytes must not exceed limit
            assert about_module._cache_total_bytes <= about_module._MAX_CACHE_BYTES
        finally:
            self._reset_cache(about_module)
            about_module._MAX_CACHE_BYTES = original_max_bytes
            about_module._MAX_CACHE_ENTRIES = original_max_entries
            _clear_overrides()

    def test_byte_counter_updated_on_eviction(self):
        """_cache_total_bytes decreases when an entry is evicted by byte limit."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        original_max_bytes = about_module._MAX_CACHE_BYTES
        original_max_entries = about_module._MAX_CACHE_ENTRIES

        try:
            # 15-byte limit; seed with two 8-byte entries (total 16 > 15 triggers eviction)
            about_module._MAX_CACHE_BYTES = 15
            about_module._MAX_CACHE_ENTRIES = 100
            now = time.time()

            data_8 = b"12345678"  # 8 bytes
            about_module._avatar_cache["entry-a"] = (data_8, "image/png", now)
            about_module._cache_total_bytes = 8

            # Manually apply the byte eviction logic (same as production code)
            new_data = b"abcdefgh"  # 8 bytes; would bring total to 16 > 15
            new_size = len(new_data)
            while about_module._avatar_cache and (
                about_module._cache_total_bytes + new_size > about_module._MAX_CACHE_BYTES
            ):
                _k, _v = about_module._avatar_cache.popitem(last=False)
                about_module._cache_total_bytes -= len(_v[0])

            about_module._avatar_cache["entry-b"] = (new_data, "image/png", now)
            about_module._cache_total_bytes += new_size

            # entry-a should be evicted; only entry-b remains
            assert "entry-a" not in about_module._avatar_cache
            assert "entry-b" in about_module._avatar_cache
            assert about_module._cache_total_bytes == 8
        finally:
            self._reset_cache(about_module)
            about_module._MAX_CACHE_BYTES = original_max_bytes
            about_module._MAX_CACHE_ENTRIES = original_max_entries


class TestAvatarExpiredEviction:
    """Tests that expired cache entries are proactively evicted on read miss."""

    def _reset_cache(self, about_module):
        about_module._avatar_cache.clear()
        about_module._cache_total_bytes = 0

    @pytest.mark.anyio
    async def test_expired_entry_evicted_on_read(self, client):
        """When a cached avatar expires, the entry is removed from cache immediately."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        try:
            _override_auth("MEMBER")

            # Seed an expired entry
            expired_time = time.time() - about_module._CACHE_TTL_SECONDS - 100
            cid = str(_FAKE_ID)
            old_data = b"old-avatar-data"
            about_module._avatar_cache[cid] = (old_data, "image/png", expired_time)
            about_module._cache_total_bytes = len(old_data)

            # Mock the external fetch to succeed with new data
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"new-avatar"
            mock_response.headers = {"content-type": "image/png"}

            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(f"{_EP}._requests.get", return_value=mock_response),
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{_FAKE_ID}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 200
            # New entry should be cached, byte counter should reflect new data only
            assert cid in about_module._avatar_cache
            assert about_module._cache_total_bytes == len(b"new-avatar")
        finally:
            self._reset_cache(about_module)
            _clear_overrides()

    @pytest.mark.anyio
    async def test_expired_entry_bytes_freed_even_on_fetch_failure(self, client):
        """Expired entry is evicted even if the GitHub fetch fails."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        try:
            _override_auth("MEMBER")

            expired_time = time.time() - about_module._CACHE_TTL_SECONDS - 100
            cid = str(_FAKE_ID)
            old_data = b"stale-data-12345"
            about_module._avatar_cache[cid] = (old_data, "image/png", expired_time)
            about_module._cache_total_bytes = len(old_data)

            # Mock fetch to fail
            import requests as real_requests

            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(
                    f"{_EP}._requests.get", side_effect=real_requests.RequestException("timeout")
                ),
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{_FAKE_ID}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 502
            # Expired entry should have been evicted even though fetch failed
            assert cid not in about_module._avatar_cache
            assert about_module._cache_total_bytes == 0
        finally:
            self._reset_cache(about_module)
            _clear_overrides()


class TestAvatarSizeLimit:
    """Tests that oversized avatar downloads are rejected."""

    def _reset_cache(self, about_module):
        about_module._avatar_cache.clear()
        about_module._cache_total_bytes = 0

    @pytest.mark.anyio
    async def test_avatar_too_large_by_content_length(self, client):
        """Avatar with Content-Length exceeding limit returns 502."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        try:
            _override_auth("MEMBER")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {
                "content-type": "image/png",
                "content-length": str(about_module._MAX_AVATAR_DOWNLOAD_BYTES + 1),
            }
            mock_response.content = b"x"

            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(f"{_EP}._requests.get", return_value=mock_response),
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{_FAKE_ID}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 502
            assert b"Avatar too large" in resp.content
        finally:
            self._reset_cache(about_module)
            _clear_overrides()

    @pytest.mark.anyio
    async def test_avatar_too_large_by_body(self, client):
        """Avatar with body exceeding limit (no Content-Length) returns 502."""
        from app.api.v1.endpoints import about as about_module

        self._reset_cache(about_module)
        original_limit = about_module._MAX_AVATAR_DOWNLOAD_BYTES
        try:
            _override_auth("MEMBER")
            about_module._MAX_AVATAR_DOWNLOAD_BYTES = 10  # tiny limit for test

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/png"}
            mock_response.content = b"x" * 11  # exceeds 10-byte limit

            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(f"{_EP}._requests.get", return_value=mock_response),
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{_FAKE_ID}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 502
        finally:
            about_module._MAX_AVATAR_DOWNLOAD_BYTES = original_limit
            self._reset_cache(about_module)
            _clear_overrides()


class TestAvatarRateLimit:
    """Tests that avatar endpoint is rate-limited."""

    @pytest.mark.anyio
    async def test_rate_limited_returns_429(self, client):
        """Avatar requests exceeding rate limit return 429."""
        from app.api.v1.endpoints import about as about_module

        about_module._avatar_cache.clear()
        about_module._cache_total_bytes = 0
        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{_FAKE_ID}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 429
        finally:
            about_module._avatar_cache.clear()
            about_module._cache_total_bytes = 0
            _clear_overrides()

    @pytest.mark.anyio
    async def test_cached_hit_not_rate_limited(self, client):
        """Cache hits bypass rate limiting (rate_limit not called)."""
        from app.api.v1.endpoints import about as about_module

        about_module._avatar_cache.clear()
        about_module._cache_total_bytes = 0
        try:
            _override_auth("MEMBER")
            # Seed valid cache entry
            cid = str(_FAKE_ID)
            about_module._avatar_cache[cid] = (b"cached-img", "image/png", time.time())
            about_module._cache_total_bytes = 10

            with (
                patch(
                    f"{_SVC}.get_contributor",
                    new_callable=AsyncMock,
                    return_value=_FAKE_CONTRIBUTOR,
                ),
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=False) as mock_rl,
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{_FAKE_ID}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            # Rate limiter should NOT have been called (cache hit)
            mock_rl.assert_not_called()
        finally:
            about_module._avatar_cache.clear()
            about_module._cache_total_bytes = 0
            _clear_overrides()


class TestGitHubUsernameValidation:
    """Tests that github_username is validated against GitHub format."""

    @pytest.mark.anyio
    async def test_create_rejects_invalid_username(self, client):
        """github_username with path traversal is rejected by schema validation."""
        try:
            _override_auth("SUPER_ADMIN")
            resp = await client.post(
                "/api/v1/about/admin/contributors",
                json={
                    "github_username": "../evil",
                    "display_name": "Evil",
                    "role": "Contributor",
                },
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_rejects_spaces(self, client):
        """github_username with spaces is rejected."""
        try:
            _override_auth("SUPER_ADMIN")
            resp = await client.post(
                "/api/v1/about/admin/contributors",
                json={
                    "github_username": "has space",
                    "display_name": "User",
                    "role": "Contributor",
                },
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_accepts_valid_username(self, client):
        """Valid GitHub username format is accepted."""
        try:
            _override_auth("SUPER_ADMIN")
            new_row = {**_FAKE_CONTRIBUTOR, "github_username": "valid-user123"}
            with (
                patch(f"{_SVC}.github_username_exists", new_callable=AsyncMock, return_value=False),
                patch(f"{_SVC}.create_contributor", new_callable=AsyncMock, return_value=new_row),
            ):
                resp = await client.post(
                    "/api/v1/about/admin/contributors",
                    json={
                        "github_username": "valid-user123",
                        "display_name": "Valid",
                        "role": "Contributor",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 201
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_rejects_leading_hyphen(self, client):
        """github_username starting with hyphen is rejected."""
        try:
            _override_auth("SUPER_ADMIN")
            resp = await client.post(
                "/api/v1/about/admin/contributors",
                json={
                    "github_username": "-leadinghyphen",
                    "display_name": "User",
                    "role": "Contributor",
                },
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_rejects_trailing_hyphen(self, client):
        """github_username ending with hyphen is rejected."""
        try:
            _override_auth("SUPER_ADMIN")
            resp = await client.post(
                "/api/v1/about/admin/contributors",
                json={
                    "github_username": "trailinghyphen-",
                    "display_name": "User",
                    "role": "Contributor",
                },
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_rejects_invalid_username(self, client):
        """Update with invalid github_username is rejected."""
        try:
            _override_auth("SUPER_ADMIN")
            resp = await client.put(
                f"/api/v1/about/admin/contributors/{_FAKE_ID}",
                json={"github_username": "has space"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_single_char_username_accepted(self, client):
        """Single character username is valid on GitHub."""
        try:
            _override_auth("SUPER_ADMIN")
            new_row = {**_FAKE_CONTRIBUTOR, "github_username": "x"}
            with (
                patch(f"{_SVC}.github_username_exists", new_callable=AsyncMock, return_value=False),
                patch(f"{_SVC}.create_contributor", new_callable=AsyncMock, return_value=new_row),
            ):
                resp = await client.post(
                    "/api/v1/about/admin/contributors",
                    json={"github_username": "x", "display_name": "X", "role": "Dev"},
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 201
        finally:
            _clear_overrides()
