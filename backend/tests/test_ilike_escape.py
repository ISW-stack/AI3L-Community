"""Tests for Bug #5: ILIKE injection — % and _ must be escaped in search suggestions."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.post_repo import _escape_ilike


class TestEscapeIlike:
    """Unit tests for the _escape_ilike helper."""

    def test_no_special_chars(self):
        assert _escape_ilike("hello") == "hello"

    def test_percent_escaped(self):
        assert _escape_ilike("100%") == "100\\%"

    def test_underscore_escaped(self):
        assert _escape_ilike("foo_bar") == "foo\\_bar"

    def test_backslash_escaped(self):
        assert _escape_ilike("a\\b") == "a\\\\b"

    def test_all_special_chars(self):
        assert _escape_ilike("%_\\") == "\\%\\_\\\\"

    def test_empty_string(self):
        assert _escape_ilike("") == ""

    def test_multiple_percents(self):
        assert _escape_ilike("%%") == "\\%\\%"

    def test_mixed_content(self):
        assert _escape_ilike("hello%world_test") == "hello\\%world\\_test"


class TestSearchSuggestionsEscape:
    """Verify that get_search_suggestions passes escaped values to SQL."""

    @pytest.mark.anyio
    async def test_percent_in_query_is_escaped(self):
        """When user searches for '%', the ILIKE param must use escaped value."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import get_search_suggestions

            result = await get_search_suggestions("%test_value", limit=5)

        assert result == []
        # The first positional arg after sql should be the escaped pattern
        call_args = mock_conn.fetch.call_args
        sql_param = call_args[0][1]
        assert sql_param == "%\\%test\\_value%"
        assert call_args[0][2] == 5

    @pytest.mark.anyio
    async def test_normal_query_unchanged(self):
        """Normal text without special chars passes through unaltered."""
        mock_conn = AsyncMock()
        fake_row = {"title": "Hello", "id": uuid.uuid4()}
        mock_conn.fetch = AsyncMock(return_value=[MagicMock(**fake_row)])

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import get_search_suggestions

            await get_search_suggestions("hello", limit=5)

        call_args = mock_conn.fetch.call_args
        sql_param = call_args[0][1]
        assert sql_param == "%hello%"


class TestKeywordSuggestionsEscape:
    """Verify that get_keyword_suggestions passes escaped values to SQL."""

    @pytest.mark.anyio
    async def test_underscore_in_query_is_escaped(self):
        """When user searches for '_', the ILIKE param must use escaped value."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import get_keyword_suggestions

            result = await get_keyword_suggestions("_test%", limit=5)

        assert result == []
        call_args = mock_conn.fetch.call_args
        sql_param = call_args[0][1]
        assert sql_param == "%\\_test\\%%"


class TestSqlContainsEscapeClause:
    """Verify the SQL strings contain ESCAPE '\\'."""

    @pytest.mark.anyio
    async def test_search_suggestions_sql_has_escape(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import get_search_suggestions

            await get_search_suggestions("test", limit=5)

        sql = mock_conn.fetch.call_args[0][0]
        assert "ESCAPE" in sql

    @pytest.mark.anyio
    async def test_keyword_suggestions_sql_has_escape(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import get_keyword_suggestions

            await get_keyword_suggestions("test", limit=5)

        sql = mock_conn.fetch.call_args[0][0]
        assert "ESCAPE" in sql
