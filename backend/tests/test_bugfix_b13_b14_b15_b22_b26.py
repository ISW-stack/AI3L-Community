"""Tests for bug fixes B-13, B-14, B-15, B-22, B-26."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EP_CO = "app.api.v1.endpoints.co_authors"
_EP_SIGS = "app.api.v1.endpoints.sigs"
_EP_APP = "app.api.v1.endpoints.applications"


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


# ── B-13: Co-authors /my-posts pagination parameter validation ─────


class TestB13CoAuthorPaginationValidation:
    """B-13: page and page_size must have Query() constraints."""

    @pytest.mark.anyio
    async def test_page_zero_rejected(self, client):
        """GET /co-authors/my-posts?page=0 → 422."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/co-authors/my-posts?page=0",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_page_negative_rejected(self, client):
        """GET /co-authors/my-posts?page=-1 → 422."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/co-authors/my-posts?page=-1",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_page_size_too_large_rejected(self, client):
        """GET /co-authors/my-posts?page_size=999999 → 422."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/co-authors/my-posts?page_size=999999",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_page_size_zero_rejected(self, client):
        """GET /co-authors/my-posts?page_size=0 → 422."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/co-authors/my-posts?page_size=0",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_valid_pagination_accepted(self, client):
        """GET /co-authors/my-posts?page=1&page_size=20 → 200."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_CO}.list_co_authored_posts",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/co-authors/my-posts?page=1&page_size=20",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_page_size_at_max_accepted(self, client):
        """GET /co-authors/my-posts?page_size=100 → 200 (at boundary)."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_CO}.list_co_authored_posts",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/co-authors/my-posts?page_size=100",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_page_size_above_max_rejected(self, client):
        """GET /co-authors/my-posts?page_size=101 → 422 (above boundary)."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/co-authors/my-posts?page_size=101",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()


# ── B-14: form_repo.find_standalone ILIKE wildcard escaping ────────


class TestB14FormRepoIlikeEscape:
    """B-14: find_standalone must escape ILIKE special chars."""

    def test_escape_ilike_percent(self):
        """_escape_ilike escapes % in form_repo."""
        from app.repositories.form_repo import _escape_ilike

        assert _escape_ilike("100%") == "100\\%"

    def test_escape_ilike_underscore(self):
        """_escape_ilike escapes _ in form_repo."""
        from app.repositories.form_repo import _escape_ilike

        assert _escape_ilike("foo_bar") == "foo\\_bar"

    def test_escape_ilike_backslash(self):
        """_escape_ilike escapes backslash in form_repo."""
        from app.repositories.form_repo import _escape_ilike

        assert _escape_ilike("a\\b") == "a\\\\b"

    @pytest.mark.anyio
    async def test_find_standalone_escapes_search_pattern(self):
        """find_standalone passes escaped ILIKE pattern to SQL."""
        from app.repositories.form_repo import find_standalone

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await find_standalone(
            mock_conn, page=1, page_size=20, user_id=uuid.uuid4(), q="%test_value"
        )

        call_args = mock_conn.fetch.call_args
        sql_param = call_args[0][3]  # $3 is the search_pattern
        assert sql_param == "%\\%test\\_value%"

    @pytest.mark.anyio
    async def test_find_standalone_sql_has_escape_clause(self):
        """find_standalone SQL contains ESCAPE '\\' for ILIKE."""
        from app.repositories.form_repo import find_standalone

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await find_standalone(mock_conn, page=1, page_size=20, user_id=uuid.uuid4(), q="test")

        sql = mock_conn.fetch.call_args[0][0]
        assert "ESCAPE" in sql

    @pytest.mark.anyio
    async def test_find_standalone_no_search_unchanged(self):
        """find_standalone without search does not use ESCAPE clause."""
        from app.repositories.form_repo import find_standalone

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await find_standalone(mock_conn, page=1, page_size=20, user_id=uuid.uuid4(), q=None)

        sql = mock_conn.fetch.call_args[0][0]
        assert "ESCAPE" not in sql


# ── B-15: user_repo.list_all must not use SELECT * ────────────────


class TestB15UserRepoListAllNoSelectStar:
    """B-15: list_all must use _USER_COLUMNS, not SELECT *."""

    @pytest.mark.anyio
    async def test_list_all_no_select_star_without_search(self, mock_pool, mock_conn):
        """list_all (no search) uses _USER_COLUMNS, not SELECT *."""
        from app.repositories.user_repo import list_all

        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            await list_all(page=1, page_size=10)

        sql = mock_conn.fetch.call_args[0][0]
        assert "SELECT *" not in sql
        assert "password_hash" not in sql
        # Should contain the specific columns
        assert "display_name" in sql
        assert "username" in sql

    @pytest.mark.anyio
    async def test_list_all_no_select_star_with_search(self, mock_pool, mock_conn):
        """list_all (with search) uses _USER_COLUMNS, not SELECT *."""
        from app.repositories.user_repo import list_all

        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            await list_all(page=1, page_size=10, search="alice")

        sql = mock_conn.fetch.call_args[0][0]
        assert "SELECT *" not in sql
        assert "password_hash" not in sql
        assert "display_name" in sql
        assert "username" in sql

    def test_user_columns_constant_excludes_password_hash(self):
        """_USER_COLUMNS must not contain password_hash."""
        from app.repositories.user_repo import _USER_COLUMNS

        assert "password_hash" not in _USER_COLUMNS

    @pytest.mark.anyio
    async def test_list_all_returns_data_correctly(self, mock_pool, mock_conn):
        """list_all returns properly structured data without password_hash."""
        from app.repositories.user_repo import list_all

        now = datetime.now(timezone.utc)
        fake_row = {
            "id": uuid.uuid4(),
            "username": "alice",
            "display_name": "Alice",
            "role": "MEMBER",
            "bio": None,
            "affiliation": None,
            "orcid": None,
            "avatar_url": None,
            "preferred_language": "en",
            "is_banned": False,
            "ban_reason": None,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "_total": 1,
        }
        mock_conn.fetch = AsyncMock(return_value=[MagicMock(**fake_row, items=fake_row.items)])

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            results, total = await list_all(page=1, page_size=10)

        # password_hash should not appear in results
        if results:
            for r in results:
                assert "password_hash" not in r


# ── B-22: SIG description sanitized on create/update ──────────────


class TestB22SigDescriptionSanitized:
    """B-22: SIG description must be sanitized with sanitize_html."""

    @pytest.mark.anyio
    async def test_create_sig_sanitizes_description(self, client, mock_pool, mock_conn):
        """POST /sigs → description is passed through sanitize_html."""
        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        sig_row = {
            "id": sig_id,
            "name": "New SIG",
            "description": "clean desc",
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        creator_row = {"display_name": "Creator"}

        mock_conn.fetchrow = AsyncMock(side_effect=[sig_row, creator_row])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP_SIGS}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP_SIGS}.sanitize_html", return_value="clean desc") as mock_sanitize,
                patch("app.services.sig.get_pool", return_value=mock_pool),
            ):
                resp = await client.post(
                    "/api/v1/sigs",
                    json={"name": "New SIG", "description": "<script>xss</script>desc"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                mock_sanitize.assert_called_once_with("<script>xss</script>desc")
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_sig_sanitizes_description(self, client):
        """PUT /sigs/{id} → description is passed through sanitize_html."""
        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc).isoformat()
        sig_result = {
            "id": str(sig_id),
            "name": "Updated SIG",
            "description": "clean desc",
            "created_by": str(uuid.uuid4()),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Creator",
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP_SIGS}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP_SIGS}.sanitize_html", return_value="clean desc") as mock_sanitize,
                patch(f"{_EP_SIGS}.update_sig", new_callable=AsyncMock, return_value=sig_result),
            ):
                resp = await client.put(
                    f"/api/v1/sigs/{sig_id}",
                    json={"name": "Updated SIG", "description": "<img onerror=alert(1)>bad"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_sanitize.assert_called_once_with("<img onerror=alert(1)>bad")
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_sig_none_description_not_sanitized(self, client, mock_pool, mock_conn):
        """POST /sigs with None description → sanitize_html not called."""
        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        sig_row = {
            "id": sig_id,
            "name": "New SIG",
            "description": None,
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        creator_row = {"display_name": "Creator"}

        mock_conn.fetchrow = AsyncMock(side_effect=[sig_row, creator_row])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP_SIGS}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP_SIGS}.sanitize_html", return_value="clean") as mock_sanitize,
                patch("app.services.sig.get_pool", return_value=mock_pool),
            ):
                await client.post(
                    "/api/v1/sigs",
                    json={"name": "New SIG"},
                    headers={"Authorization": "Bearer fake"},
                )
                # Should not have called sanitize_html when description is None
                mock_sanitize.assert_not_called()
        finally:
            _clear_overrides()


# ── B-26: Application review audit emit wrapped in try/except ─────


class TestB26AuditEmitTryExcept:
    """B-26: Audit emit failure must not cause 500 on application review."""

    @pytest.mark.anyio
    async def test_review_succeeds_when_emit_fails(self, client):
        """PUT /admin/applications/{id}/review → 200 even when emit raises."""
        app_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        app_row = {
            "id": app_id,
            "user_id": uuid.uuid4(),
            "username": "guest1",
            "display_name": "Guest User",
            "description": "I'd like to join",
            "status": "APPROVED",
            "reviewed_by": uuid.uuid4(),
            "reviewed_at": now,
            "created_at": now,
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(
                    f"{_EP_APP}.review_application",
                    new_callable=AsyncMock,
                    return_value=app_row,
                ),
                patch(
                    f"{_EP_APP}.emit",
                    new_callable=AsyncMock,
                    side_effect=ConnectionError("Redis connection refused"),
                ),
            ):
                resp = await client.put(
                    f"/api/v1/admin/applications/{app_id}/review",
                    json={"action": "APPROVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                # Must still return 200 despite emit failure
                assert resp.status_code == 200
                assert "approved" in resp.json()["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_review_succeeds_when_emit_succeeds(self, client):
        """PUT /admin/applications/{id}/review → 200 when emit succeeds normally."""
        app_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        app_row = {
            "id": app_id,
            "user_id": uuid.uuid4(),
            "username": "guest1",
            "display_name": "Guest User",
            "description": "I'd like to join",
            "status": "REJECTED",
            "reviewed_by": uuid.uuid4(),
            "reviewed_at": now,
            "created_at": now,
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(
                    f"{_EP_APP}.review_application",
                    new_callable=AsyncMock,
                    return_value=app_row,
                ),
                patch(f"{_EP_APP}.emit", new_callable=AsyncMock) as mock_emit,
            ):
                resp = await client.put(
                    f"/api/v1/admin/applications/{app_id}/review",
                    json={"action": "REJECTED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                # emit should have been called
                mock_emit.assert_called_once()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_review_emit_timeout_does_not_crash(self, client):
        """PUT /admin/applications/{id}/review → 200 on emit TimeoutError."""
        app_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        app_row = {
            "id": app_id,
            "user_id": uuid.uuid4(),
            "username": "guest1",
            "display_name": "Guest User",
            "description": "I'd like to join",
            "status": "APPROVED",
            "reviewed_by": uuid.uuid4(),
            "reviewed_at": now,
            "created_at": now,
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(
                    f"{_EP_APP}.review_application",
                    new_callable=AsyncMock,
                    return_value=app_row,
                ),
                patch(
                    f"{_EP_APP}.emit",
                    new_callable=AsyncMock,
                    side_effect=TimeoutError("Redis timeout"),
                ),
            ):
                resp = await client.put(
                    f"/api/v1/admin/applications/{app_id}/review",
                    json={"action": "APPROVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()
