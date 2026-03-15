"""Tests for form_repo.find_responses LEFT JOIN fix (Bug #3).

Verifies that find_responses uses LEFT JOIN so guest responses
(with user_ids not in the users table) are included in results
with fallback display_name='Guest' and username='guest'.
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories import form_repo


def _make_response_row(
    user_id: uuid.UUID,
    display_name: str | None = None,
    username: str | None = None,
    answers: dict | None = None,
):
    """Create a mock row dict simulating a LEFT JOIN result."""
    return {
        "id": uuid.uuid4(),
        "form_id": uuid.uuid4(),
        "user_id": user_id,
        "answers": json.dumps(answers or {"q1": "answer"}),
        "created_at": datetime.now(timezone.utc),
        "display_name": display_name,
        "username": username,
    }


class TestFindResponsesLeftJoin:
    """find_responses should return guest responses via LEFT JOIN."""

    @pytest.mark.asyncio
    async def test_guest_response_included_with_fallback_names(self, mock_pool, mock_conn):
        """A response with no matching user should get 'Guest'/'guest' defaults."""
        form_id = uuid.uuid4()
        guest_user_id = uuid.uuid4()

        # Simulate LEFT JOIN result: NULL user fields become COALESCE defaults
        guest_row = _make_response_row(
            user_id=guest_user_id,
            display_name="Guest",  # COALESCE(u.display_name, 'Guest')
            username="guest",  # COALESCE(u.username, 'guest')
        )

        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[guest_row])

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            results, total = await form_repo.find_responses(form_id)

        assert total == 1
        assert len(results) == 1
        assert results[0]["display_name"] == "Guest"
        assert results[0]["username"] == "guest"
        assert results[0]["user_id"] == guest_user_id

    @pytest.mark.asyncio
    async def test_registered_user_response_has_real_names(self, mock_pool, mock_conn):
        """A response from a registered user should show their real name."""
        form_id = uuid.uuid4()
        user_id = uuid.uuid4()

        user_row = _make_response_row(
            user_id=user_id,
            display_name="Alice",
            username="alice",
        )

        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[user_row])

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            results, total = await form_repo.find_responses(form_id)

        assert total == 1
        assert results[0]["display_name"] == "Alice"
        assert results[0]["username"] == "alice"

    @pytest.mark.asyncio
    async def test_mixed_guest_and_user_responses(self, mock_pool, mock_conn):
        """Both guest and registered user responses should be returned."""
        form_id = uuid.uuid4()

        rows = [
            _make_response_row(uuid.uuid4(), "Alice", "alice"),
            _make_response_row(uuid.uuid4(), "Guest", "guest"),
            _make_response_row(uuid.uuid4(), "Bob", "bob"),
        ]

        mock_conn.fetchval = AsyncMock(return_value=3)
        mock_conn.fetch = AsyncMock(return_value=rows)

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            results, total = await form_repo.find_responses(form_id)

        assert total == 3
        assert len(results) == 3
        names = [r["display_name"] for r in results]
        assert "Guest" in names
        assert "Alice" in names
        assert "Bob" in names

    @pytest.mark.asyncio
    async def test_answers_json_string_is_parsed(self, mock_pool, mock_conn):
        """Answers stored as JSON string should be parsed into a dict."""
        form_id = uuid.uuid4()

        row = _make_response_row(uuid.uuid4(), "Guest", "guest", answers={"q1": "yes", "q2": 5})

        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[row])

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            results, _ = await form_repo.find_responses(form_id)

        assert isinstance(results[0]["answers"], dict)
        assert results[0]["answers"]["q1"] == "yes"
        assert results[0]["answers"]["q2"] == 5

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_pool, mock_conn):
        """No responses should return empty list and zero total."""
        form_id = uuid.uuid4()

        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            results, total = await form_repo.find_responses(form_id)

        assert total == 0
        assert results == []

    @pytest.mark.asyncio
    async def test_query_uses_left_join(self, mock_pool, mock_conn):
        """Verify the SQL query passed to fetch contains LEFT JOIN."""
        form_id = uuid.uuid4()
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            await form_repo.find_responses(form_id)

        # Inspect the SQL query passed to conn.fetch
        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "LEFT JOIN" in sql
        assert "COALESCE" in sql
