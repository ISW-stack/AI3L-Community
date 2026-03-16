"""Tests for SQL/repository security fixes: S03, S08, S15.

S03 — ILIKE wildcard injection in user search
S08 — SELECT */RETURNING * exposing password_hash
S15 — reaction_helpers table name interpolation
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_user_dict


# ---------------------------------------------------------------------------
# S03: ILIKE wildcard injection — _escape_ilike + search_users_for_coauthor
# ---------------------------------------------------------------------------


class TestEscapeIlike:
    """Unit tests for the _escape_ilike helper."""

    def test_plain_string_unchanged(self):
        from app.repositories.user_repo import _escape_ilike

        assert _escape_ilike("alice") == "alice"

    def test_percent_escaped(self):
        from app.repositories.user_repo import _escape_ilike

        assert _escape_ilike("100%") == "100\\%"

    def test_underscore_escaped(self):
        from app.repositories.user_repo import _escape_ilike

        assert _escape_ilike("a_b") == "a\\_b"

    def test_backslash_escaped(self):
        from app.repositories.user_repo import _escape_ilike

        assert _escape_ilike("a\\b") == "a\\\\b"

    def test_all_special_chars(self):
        from app.repositories.user_repo import _escape_ilike

        assert _escape_ilike("%_\\") == "\\%\\_\\\\"


class TestSearchUsersForCoauthor:
    """Repository-level tests for search_users_for_coauthor."""

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_normal_search(self, mock_get_pool, mock_pool, mock_conn):
        """Normal search term passes through to ILIKE and returns results."""
        from app.repositories.user_repo import search_users_for_coauthor

        uid = uuid.uuid4()
        mock_conn.fetch.return_value = [
            {"id": uid, "username": "alice", "display_name": "Alice Smith", "avatar_url": None},
        ]
        mock_get_pool.return_value = mock_pool

        results = await search_users_for_coauthor("alice", limit=5)

        assert len(results) == 1
        assert results[0]["username"] == "alice"
        # Verify the pattern passed to the query uses escaped value
        call_args = mock_conn.fetch.call_args
        pattern_arg = call_args[0][1]  # second positional arg ($1)
        assert pattern_arg == "%alice%"

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_percent_in_query_escaped(self, mock_get_pool, mock_pool, mock_conn):
        """A '%' in the search query is escaped so it does not act as a wildcard."""
        from app.repositories.user_repo import search_users_for_coauthor

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        await search_users_for_coauthor("%", limit=5)

        call_args = mock_conn.fetch.call_args
        pattern_arg = call_args[0][1]
        # The percent should be escaped: %\%% (wrapped in wildcards)
        assert pattern_arg == "%\\%%"

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_underscore_in_query_escaped(self, mock_get_pool, mock_pool, mock_conn):
        """An '_' in the search query is escaped so it does not match single chars."""
        from app.repositories.user_repo import search_users_for_coauthor

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        await search_users_for_coauthor("_", limit=5)

        call_args = mock_conn.fetch.call_args
        pattern_arg = call_args[0][1]
        assert pattern_arg == "%\\_%"

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_empty_results(self, mock_get_pool, mock_pool, mock_conn):
        """Non-matching query returns empty list."""
        from app.repositories.user_repo import search_users_for_coauthor

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        results = await search_users_for_coauthor("zzz_nonexistent_zzz", limit=5)
        assert results == []

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_sql_escape_clause_present(self, mock_get_pool, mock_pool, mock_conn):
        """The SQL query must contain ESCAPE '\\' for the escaping to take effect."""
        from app.repositories.user_repo import search_users_for_coauthor

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        await search_users_for_coauthor("test", limit=5)

        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "ESCAPE" in sql


class TestSearchEndpointUsesRepo:
    """Verify the /users/search endpoint delegates to search_users_for_coauthor."""

    @pytest.mark.anyio
    async def test_endpoint_delegates_to_repo(self, client):
        from app.core.deps import get_current_user, require_role
        from app.main import app

        uid = str(uuid.uuid4())
        result_id = uuid.uuid4()
        payload = {"sub": uid, "role": "MEMBER", "jti": str(uuid.uuid4())}
        app.dependency_overrides[get_current_user] = lambda: payload
        # require_role returns a dependency function; override to just return payload
        app.dependency_overrides[require_role("SUPER_ADMIN", "ADMIN", "MEMBER")] = lambda: payload

        try:
            with (
                patch(
                    "app.repositories.user_repo.search_users_for_coauthor",
                    new_callable=AsyncMock,
                    return_value=[
                        {
                            "id": result_id,
                            "username": "alice",
                            "display_name": "Alice",
                            "avatar_url": None,
                        },
                    ],
                ) as mock_search,
                patch(
                    "app.converters.user_converter.async_resolve_avatar_url",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.get("/api/v1/users/search?q=alice")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 1
                assert data[0]["username"] == "alice"
                mock_search.assert_called_once_with("alice", 5)
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# S08: SELECT * / RETURNING * exposing password_hash
# ---------------------------------------------------------------------------


def _make_safe_user_row(user_id=None, username="testuser"):
    """Create a mock row dict WITHOUT password_hash (simulating _USER_COLUMNS)."""
    uid = user_id or uuid.uuid4()
    now = datetime.now(timezone.utc)
    return {
        "id": uid,
        "username": username,
        "display_name": username,
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
    }


class TestUserColumnsConstant:
    """Verify _USER_COLUMNS excludes password_hash."""

    def test_password_hash_not_in_columns(self):
        from app.repositories.user_repo import _USER_COLUMNS

        assert "password_hash" not in _USER_COLUMNS

    def test_required_columns_present(self):
        from app.repositories.user_repo import _USER_COLUMNS

        for col in [
            "id", "username", "display_name", "role", "bio",
            "affiliation", "orcid", "avatar_url", "preferred_language",
            "is_banned", "ban_reason", "is_deleted", "created_at", "updated_at",
        ]:
            assert col in _USER_COLUMNS, f"Missing column: {col}"


class TestFindByIdNoPasswordHash:
    """find_by_id should use _USER_COLUMNS (no password_hash in result)."""

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_find_by_id_no_password_hash(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.user_repo import _USER_COLUMNS, find_by_id

        uid = uuid.uuid4()
        safe_row = _make_safe_user_row(user_id=uid)
        mock_conn.fetchrow.return_value = safe_row
        mock_get_pool.return_value = mock_pool

        result = await find_by_id(uid)

        assert result is not None
        assert "password_hash" not in result
        # Verify the SQL contains _USER_COLUMNS, not SELECT *
        sql = mock_conn.fetchrow.call_args[0][0]
        assert "password_hash" not in sql
        assert "SELECT" in sql
        assert "*" not in sql.split("FROM")[0]  # no * in SELECT clause


class TestInsertNoPasswordHash:
    """insert should RETURNING _USER_COLUMNS (no password_hash in result)."""

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_insert_no_password_hash(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.user_repo import insert

        uid = uuid.uuid4()
        safe_row = _make_safe_user_row(user_id=uid, username="newuser")
        mock_conn.fetchrow.return_value = safe_row
        mock_get_pool.return_value = mock_pool

        result = await insert(uid, "newuser", "hashed_pw", "MEMBER", "newuser")

        assert result is not None
        assert "password_hash" not in result
        # Verify RETURNING clause does not use *
        sql = mock_conn.fetchrow.call_args[0][0]
        returning_part = sql.split("RETURNING")[1]
        assert "*" not in returning_part


class TestUpdateProfileNoPasswordHash:
    """update_profile should RETURNING _USER_COLUMNS (no password_hash)."""

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_update_profile_no_password_hash(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.user_repo import update_profile

        uid = uuid.uuid4()
        safe_row = _make_safe_user_row(user_id=uid)
        safe_row["display_name"] = "Updated Name"
        mock_conn.fetchrow.return_value = safe_row
        mock_get_pool.return_value = mock_pool

        result = await update_profile(uid, display_name="Updated Name")

        assert result is not None
        assert "password_hash" not in result
        sql = mock_conn.fetchrow.call_args[0][0]
        returning_part = sql.split("RETURNING")[1]
        assert "*" not in returning_part


class TestUpdateRoleNoPasswordHash:
    """update_role should RETURNING _USER_COLUMNS (no password_hash)."""

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_update_role_no_password_hash(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.user_repo import update_role

        uid = uuid.uuid4()
        safe_row = _make_safe_user_row(user_id=uid)
        safe_row["role"] = "ADMIN"
        mock_conn.fetchrow.return_value = safe_row
        mock_get_pool.return_value = mock_pool

        result = await update_role(uid, "ADMIN")

        assert result is not None
        assert "password_hash" not in result
        sql = mock_conn.fetchrow.call_args[0][0]
        returning_part = sql.split("RETURNING")[1]
        assert "*" not in returning_part


class TestFindByUsernameStillHasPasswordHash:
    """find_by_username must still use SELECT * (needed for authentication)."""

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_find_by_username_has_password_hash(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.user_repo import find_by_username

        full_row = make_user_dict(username="alice")
        mock_conn.fetchrow.return_value = full_row
        mock_get_pool.return_value = mock_pool

        result = await find_by_username("alice")

        assert result is not None
        assert "password_hash" in result
        # Verify the SQL uses SELECT *
        sql = mock_conn.fetchrow.call_args[0][0]
        assert "SELECT *" in sql


class TestFindPasswordHashStillWorks:
    """find_password_hash should still return the hash for password change flows."""

    @pytest.mark.asyncio
    @patch("app.repositories.user_repo.get_pool")
    async def test_find_password_hash(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.user_repo import find_password_hash

        uid = uuid.uuid4()
        mock_conn.fetchrow.return_value = {"password_hash": "$argon2id$v=19$fake$hash"}
        mock_get_pool.return_value = mock_pool

        result = await find_password_hash(uid)
        assert result == "$argon2id$v=19$fake$hash"


# ---------------------------------------------------------------------------
# S15: reaction_helpers table name interpolation → query dictionary
# ---------------------------------------------------------------------------


class TestReactionHelpersQueryDict:
    """Verify _QUERIES dictionary replaces f-string table interpolation."""

    def test_queries_dict_has_expected_tables(self):
        from app.repositories.reaction_helpers import _QUERIES

        assert "posts" in _QUERIES
        assert "comments" in _QUERIES
        assert len(_QUERIES) == 2

    def test_queries_dict_has_select_and_update(self):
        from app.repositories.reaction_helpers import _QUERIES

        for table in ("posts", "comments"):
            assert "select" in _QUERIES[table]
            assert "update" in _QUERIES[table]

    def test_queries_contain_correct_table_names(self):
        from app.repositories.reaction_helpers import _QUERIES

        assert "FROM posts" in _QUERIES["posts"]["select"]
        assert "FROM comments" in _QUERIES["comments"]["select"]
        assert "UPDATE posts" in _QUERIES["posts"]["update"]
        assert "UPDATE comments" in _QUERIES["comments"]["update"]


class TestReactionHelpersInvalidTable:
    """Invalid table names must raise ValueError — SQL injection blocked."""

    @pytest.mark.asyncio
    async def test_invalid_table_raises_valueerror(self):
        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        fake_conn = AsyncMock()
        with pytest.raises(ValueError, match="Invalid table"):
            await toggle_reaction_jsonb(
                fake_conn, "evil_table", str(uuid.uuid4()), "user1", "LIKE"
            )

    @pytest.mark.asyncio
    async def test_sql_injection_table_name(self):
        """SQL injection attempt via table name is blocked."""
        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        fake_conn = AsyncMock()
        with pytest.raises(ValueError, match="Invalid table"):
            await toggle_reaction_jsonb(
                fake_conn,
                "posts; DROP TABLE users; --",
                str(uuid.uuid4()),
                "user1",
                "LIKE",
            )

    @pytest.mark.asyncio
    async def test_empty_table_name(self):
        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        fake_conn = AsyncMock()
        with pytest.raises(ValueError, match="Invalid table"):
            await toggle_reaction_jsonb(
                fake_conn, "", str(uuid.uuid4()), "user1", "LIKE"
            )


class TestReactionHelpersValidTables:
    """Valid table names ('posts', 'comments') work correctly with query dict."""

    @pytest.mark.asyncio
    async def test_posts_table_works(self):
        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        fake_conn = AsyncMock()
        row_id = uuid.uuid4()
        fake_conn.fetchrow.return_value = {"reactions": None}

        result = await toggle_reaction_jsonb(fake_conn, "posts", row_id, "user1", "LIKE")

        assert result == {"LIKE": ["user1"]}
        # Verify the SELECT query used is from _QUERIES["posts"]
        select_sql = fake_conn.fetchrow.call_args[0][0]
        assert "FROM posts" in select_sql
        assert "FOR UPDATE" in select_sql

    @pytest.mark.asyncio
    async def test_comments_table_works(self):
        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        fake_conn = AsyncMock()
        row_id = uuid.uuid4()
        fake_conn.fetchrow.return_value = {"reactions": None}

        result = await toggle_reaction_jsonb(fake_conn, "comments", row_id, "user1", "LIKE")

        assert result == {"LIKE": ["user1"]}
        select_sql = fake_conn.fetchrow.call_args[0][0]
        assert "FROM comments" in select_sql

    @pytest.mark.asyncio
    async def test_no_fstring_interpolation_in_queries(self):
        """Ensure no f-string or format-string patterns exist — queries are static strings."""
        from app.repositories.reaction_helpers import _QUERIES

        for table, queries in _QUERIES.items():
            for query_type, sql in queries.items():
                # No curly braces (f-string placeholders) should exist in the SQL
                assert "{" not in sql, f"Found '{{' in _QUERIES[{table}][{query_type}]"
                assert "}" not in sql, f"Found '}}' in _QUERIES[{table}][{query_type}]"
