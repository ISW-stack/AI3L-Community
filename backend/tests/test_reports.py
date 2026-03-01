"""Tests for reports endpoints — report post, list reports, review report."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.reports"


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
