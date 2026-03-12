"""Tests for reports endpoints — report post, list reports, review report.
Also covers atomic check+insert transaction safety in report_repo.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.reports"
_REPO = "app.repositories.report_repo"


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


def _make_report(post_id=None, user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "post_id": str(post_id or uuid.uuid4()),
        "user_id": user_id or str(uuid.uuid4()),
        "reason": "Spam content",
        "status": "PENDING",
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": now,
    }


class TestReportPost:
    @pytest.mark.anyio
    async def test_report_post(self, client):
        """POST /posts/{pid}/report → 201."""
        post_id = uuid.uuid4()
        report = _make_report(post_id=post_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value={"id": post_id}
                ),
                patch(f"{_EP}.create_report", new_callable=AsyncMock, return_value=report),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/report",
                    json={"reason": "Spam content"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["reason"] == "Spam content"
        finally:
            _clear_overrides()


class TestListReports:
    @pytest.mark.anyio
    async def test_list_reports(self, client):
        """GET /admin/reports → 200."""
        report = _make_report()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.list_reports", new_callable=AsyncMock, return_value=([report], 1)):
                resp = await client.get(
                    "/api/v1/admin/reports",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["reports"]) == 1
        finally:
            _clear_overrides()


class TestReviewReport:
    @pytest.mark.anyio
    async def test_review_report(self, client):
        """PUT /admin/reports/{id}/review → 200."""
        report_id = uuid.uuid4()
        report = _make_report()
        report["status"] = "RESOLVED"
        report["reviewed_by"] = str(uuid.uuid4())
        report["reviewed_at"] = datetime.now(timezone.utc).isoformat()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.review_report", new_callable=AsyncMock, return_value=report):
                resp = await client.put(
                    f"/api/v1/admin/reports/{report_id}/review",
                    json={"status": "RESOLVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["status"] == "RESOLVED"
        finally:
            _clear_overrides()


class TestReportPostNotFound:
    @pytest.mark.anyio
    async def test_report_post_not_found(self, client):
        """POST /posts/{id}/report → 404 when post does not exist."""
        post_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value=None),
                patch(f"{_EP}.create_report", new_callable=AsyncMock),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/report",
                    json={"reason": "Spam content"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestReportPostDuplicate:
    @pytest.mark.anyio
    async def test_report_post_duplicate(self, client):
        """POST /posts/{id}/report → 409 when ValueError raised (duplicate report)."""
        post_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.get_post_by_id",
                    new_callable=AsyncMock,
                    return_value={"id": post_id},
                ),
                patch(
                    f"{_EP}.create_report",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Already reported."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/report",
                    json={"reason": "Spam content"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                assert "already reported" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestReportPostRateLimit:
    @pytest.mark.anyio
    async def test_report_post_rate_limited(self, client):
        """POST /posts/{pid}/report → 429 when rate limited."""
        post_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/report",
                    json={"reason": "Spam content"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestReviewReportNotFound:
    @pytest.mark.anyio
    async def test_review_report_not_found(self, client):
        """PUT /admin/reports/{id}/review → 404 when report does not exist."""
        report_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.review_report", new_callable=AsyncMock, return_value=None):
                resp = await client.put(
                    f"/api/v1/admin/reports/{report_id}/review",
                    json={"status": "RESOLVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestListReportsWithPostTitle:
    @pytest.mark.anyio
    async def test_list_reports_includes_post_title(self, client):
        """GET /admin/reports → 200 includes post_title field from joined posts table."""
        report = _make_report()
        report["post_title"] = "My Test Post"

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.list_reports", new_callable=AsyncMock, return_value=([report], 1)):
                resp = await client.get(
                    "/api/v1/admin/reports",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["reports"][0]["post_title"] == "My Test Post"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_reports_post_title_null_when_post_deleted(self, client):
        """GET /admin/reports → 200 with post_title=null when post was deleted."""
        report = _make_report()
        report["post_title"] = None

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.list_reports", new_callable=AsyncMock, return_value=([report], 1)):
                resp = await client.get(
                    "/api/v1/admin/reports",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["reports"][0]["post_title"] is None
        finally:
            _clear_overrides()


class TestListReportsFiltered:
    @pytest.mark.anyio
    async def test_list_reports_with_status_filter(self, client):
        """GET /admin/reports with status filter → 200 returns filtered reports."""
        report = _make_report()
        report["status"] = "PENDING"

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.list_reports",
                new_callable=AsyncMock,
                return_value=([report], 1),
            ):
                resp = await client.get(
                    "/api/v1/admin/reports?status_filter=PENDING",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert data["reports"][0]["status"] == "PENDING"
        finally:
            _clear_overrides()


class TestReportInsertTransaction:
    """Verify report_repo.insert wraps check+insert in a transaction."""

    @pytest.mark.anyio
    async def test_insert_no_duplicate_uses_transaction(self, mock_pool, mock_conn):
        """insert() must open a transaction and insert when no duplicate report exists."""
        from app.repositories.report_repo import insert

        report_id = uuid.uuid4()
        post_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        new_row = {
            "id": report_id,
            "post_id": post_id,
            "user_id": user_id,
            "reason": "Spam",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": now,
            "updated_at": now,
        }

        # fetchval returns None (no existing pending report), fetchrow returns new row
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=new_row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await insert(report_id, post_id, user_id, "Spam")

        assert result is not None
        assert result["id"] == report_id
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_insert_duplicate_returns_none_uses_transaction(self, mock_pool, mock_conn):
        """insert() returns None for duplicate report, inside a transaction."""
        from app.repositories.report_repo import insert

        report_id = uuid.uuid4()
        post_id = uuid.uuid4()
        user_id = uuid.uuid4()
        existing_report_id = uuid.uuid4()

        # fetchval returns an existing report id (duplicate)
        mock_conn.fetchval = AsyncMock(return_value=existing_report_id)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await insert(report_id, post_id, user_id, "Spam again")

        assert result is None
        # INSERT should NOT have been called
        mock_conn.fetchrow.assert_not_called()
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_insert_concurrent_only_one_succeeds(self, mock_pool, mock_conn):
        """Simulate concurrent report inserts: second call sees duplicate and returns None."""
        import asyncio

        from app.repositories.report_repo import insert

        post_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        call_count = 0

        async def fetchval_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call: no duplicate; second call: sees the first report as existing
            return None if call_count == 1 else uuid.uuid4()

        new_row = {
            "id": uuid.uuid4(),
            "post_id": post_id,
            "user_id": user_id,
            "reason": "Spam",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        mock_conn.fetchval = AsyncMock(side_effect=fetchval_side_effect)
        mock_conn.fetchrow = AsyncMock(return_value=new_row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            results = await asyncio.gather(
                insert(uuid.uuid4(), post_id, user_id, "Spam"),
                insert(uuid.uuid4(), post_id, user_id, "Spam"),
            )

        non_none = [r for r in results if r is not None]
        none_results = [r for r in results if r is None]
        assert len(non_none) == 1
        assert len(none_results) == 1
        assert mock_conn.transaction.call_count == 2
