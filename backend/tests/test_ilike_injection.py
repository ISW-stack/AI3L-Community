"""Tests for ILIKE injection prevention in user search (H1/H2/H3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.user_repo import _escape_ilike


class TestUserRepoEscapeIlike:
    """Unit tests for user_repo._escape_ilike helper."""

    def test_percent_escaped(self) -> None:
        assert _escape_ilike("100%") == "100\\%"

    def test_underscore_escaped(self) -> None:
        assert _escape_ilike("foo_bar") == "foo\\_bar"

    def test_backslash_escaped(self) -> None:
        assert _escape_ilike("a\\b") == "a\\\\b"

    def test_all_special_chars(self) -> None:
        assert _escape_ilike("%_\\") == "\\%\\_\\\\"

    def test_no_special_chars(self) -> None:
        assert _escape_ilike("hello") == "hello"

    def test_empty_string(self) -> None:
        assert _escape_ilike("") == ""


def _make_mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Create a mock pool + connection pair following project conventions."""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm
    return mock_pool, mock_conn


class TestSearchUsersEscape:
    """Verify that search_users applies ILIKE escaping."""

    @pytest.mark.anyio
    async def test_special_chars_escaped_in_query(self) -> None:
        """Special characters in search query must be escaped before SQL."""
        mock_pool, mock_conn = _make_mock_pool()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import search_users

            result = await search_users("%admin_test", limit=10)

        assert result == []
        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        pattern_param = call_args[0][1]
        limit_param = call_args[0][2]

        # Pattern must have escaped special chars
        assert pattern_param == "%\\%admin\\_test%"
        assert limit_param == 10
        # SQL must contain ESCAPE clause
        assert "ESCAPE" in sql

    @pytest.mark.anyio
    async def test_normal_query_passes_through(self) -> None:
        """Normal text without special chars is wrapped in % but not altered."""
        mock_pool, mock_conn = _make_mock_pool()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import search_users

            await search_users("alice", limit=5)

        pattern_param = mock_conn.fetch.call_args[0][1]
        assert pattern_param == "%alice%"


class TestListAllSearchEscape:
    """Verify that list_all escapes ILIKE when search is provided."""

    @pytest.mark.anyio
    async def test_search_pattern_escaped(self) -> None:
        """list_all must escape %, _, \\ in the search parameter."""
        mock_pool, mock_conn = _make_mock_pool()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import list_all

            users, total = await list_all(page=1, page_size=10, search="test%_value")

        assert users == []
        assert total == 0
        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        pattern_param = call_args[0][1]

        # Special chars must be escaped
        assert pattern_param == "%test\\%\\_value%"
        # SQL must include ESCAPE clause
        assert "ESCAPE" in sql

    @pytest.mark.anyio
    async def test_no_search_skips_ilike(self) -> None:
        """list_all without search should not use ILIKE at all."""
        mock_pool, mock_conn = _make_mock_pool()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import list_all

            await list_all(page=1, page_size=10, search=None)

        sql = mock_conn.fetch.call_args[0][0]
        assert "ILIKE" not in sql
