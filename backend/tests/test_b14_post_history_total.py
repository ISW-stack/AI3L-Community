"""B14: Post history total reflects actual count, not capped length."""

import uuid
from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_history_row(version: int = 1) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "post_id": uuid.uuid4(),
        "version": version,
        "title": f"Title v{version}",
        "content": f"Content v{version}",
        "edited_at": now,
    }


class TestFindHistoryReturnsTotal:
    """post_repo.find_history now returns (rows, total) using COUNT(*) OVER()."""

    @patch("app.repositories.post_repo.get_pool")
    async def test_total_reflects_actual_count_when_capped(
        self, mock_get_pool: Any, mock_pool: Any, mock_conn: Any
    ) -> None:
        """When there are 100 history rows but limit=50, total should be 100."""
        from app.repositories.post_repo import find_history

        # Simulate 50 rows returned (capped) but _total_count says 100
        rows = []
        for i in range(50):
            row = _make_history_row(version=i + 1)
            row["_total_count"] = 100
            rows.append(row)

        mock_conn.fetch.return_value = rows
        mock_get_pool.return_value = mock_pool

        result_rows, total = await find_history(uuid.uuid4())
        assert total == 100
        assert len(result_rows) == 50
        # _total_count should be stripped from result dicts
        for r in result_rows:
            assert "_total_count" not in r

    @patch("app.repositories.post_repo.get_pool")
    async def test_total_equals_length_when_under_limit(
        self, mock_get_pool: Any, mock_pool: Any, mock_conn: Any
    ) -> None:
        """When there are fewer rows than limit, total equals len(rows)."""
        from app.repositories.post_repo import find_history

        rows = []
        for i in range(3):
            row = _make_history_row(version=i + 1)
            row["_total_count"] = 3
            rows.append(row)

        mock_conn.fetch.return_value = rows
        mock_get_pool.return_value = mock_pool

        result_rows, total = await find_history(uuid.uuid4())
        assert total == 3
        assert len(result_rows) == 3

    @patch("app.repositories.post_repo.get_pool")
    async def test_empty_history_returns_zero_total(
        self, mock_get_pool: Any, mock_pool: Any, mock_conn: Any
    ) -> None:
        """When there are no history rows, total should be 0."""
        from app.repositories.post_repo import find_history

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        result_rows, total = await find_history(uuid.uuid4())
        assert total == 0
        assert result_rows == []

    @patch("app.repositories.post_repo.get_pool")
    async def test_sql_uses_count_over(
        self, mock_get_pool: Any, mock_pool: Any, mock_conn: Any
    ) -> None:
        """The SQL query should use COUNT(*) OVER() for total count."""
        from app.repositories.post_repo import find_history

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        await find_history(uuid.uuid4())
        sql = mock_conn.fetch.call_args[0][0]
        assert "COUNT(*) OVER()" in sql


class TestGetPostHistoryService:
    """service get_post_history passes through total from repo."""

    @patch("app.repositories.post_repo.get_pool")
    async def test_service_returns_total(
        self, mock_get_pool: Any, mock_pool: Any, mock_conn: Any
    ) -> None:
        from app.services.post import get_post_history

        now = datetime.now(timezone.utc)
        row = {
            "id": uuid.uuid4(),
            "post_id": uuid.uuid4(),
            "version": 1,
            "title": "V1",
            "content": "body",
            "edited_at": now,
            "_total_count": 75,
        }
        mock_conn.fetch.return_value = [row]
        mock_get_pool.return_value = mock_pool

        history, total = await get_post_history(uuid.uuid4())
        assert total == 75
        assert len(history) == 1
        assert history[0]["version"] == 1


class TestPostHistoryEndpoint:
    """Endpoint uses actual total from service, not len(history)."""

    @patch("app.api.v1.endpoints.posts.get_post_history")
    @patch("app.api.v1.endpoints.posts.get_post_by_id")
    async def test_endpoint_returns_actual_total(
        self, mock_get_post: Any, mock_get_history: Any, client: Any
    ) -> None:
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        post_id = uuid.uuid4()

        mock_get_post.return_value = {
            "author": {"id": user_id},
        }
        # Service returns 5 items but total=100
        history_items = [
            {
                "id": str(uuid.uuid4()),
                "version": i + 1,
                "title": f"Title v{i + 1}",
                "content": f"Content v{i + 1}",
                "edited_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(5)
        ]
        mock_get_history.return_value = (history_items, 100)

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": user_id,
            "role": "MEMBER",
            "jti": "jti-1",
        }
        try:
            resp = await client.get(
                f"/api/v1/posts/{post_id}/history",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 100
            assert len(data["history"]) == 5
        finally:
            app.dependency_overrides.pop(get_current_user, None)
