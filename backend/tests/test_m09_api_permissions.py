"""Tests for audit findings M-09, M-10, M-14, M-38, L-05, L-06, L-07, L-08, L-09.

Covers:
- M-09: Co-author list-all ownership check
- M-10: QA rate limiting on mark_best_answer and vote_on_answer
- M-38: Task ownership fail-closed when Redis key expired
- L-05: File scan status ownership verification
- L-06: about/members page param upper bound
- L-07: Preferences/notifications block GUEST
- L-08: Avatar upload blocks GUEST
- L-09: Delete account blocks GUEST
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

_QA_EP = "app.api.v1.endpoints.qa"
_TASKS_EP = "app.api.v1.endpoints.tasks"
_FILES_EP = "app.api.v1.endpoints.files"
_COAUTHOR_SVC = "app.services.co_author"


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": uid,
        "role": role,
        "jti": "jti-test",
    }
    return uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


# ── M-09: Co-author list-all ownership check ────────────────────────────


class TestM09CoAuthorOwnershipCheck:
    """M-09: list_all_co_authors should require post ownership or admin role."""

    @pytest.mark.anyio
    async def test_non_owner_member_cannot_list_all_co_authors(self):
        """A MEMBER who is not the post owner should get 403."""
        from app.core.errors import ForbiddenError
        from app.services.co_author import list_all_co_authors

        post_id = uuid.uuid4()
        owner_id = str(uuid.uuid4())
        caller_id = str(uuid.uuid4())  # different user

        post_row = {"id": post_id, "user_id": uuid.UUID(owner_id)}

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=post_row)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch(f"{_COAUTHOR_SVC}.get_pool", return_value=mock_pool):
            with pytest.raises(ForbiddenError):
                await list_all_co_authors(
                    post_id=post_id, user_id=caller_id, is_admin=False
                )

    @pytest.mark.anyio
    async def test_owner_can_list_all_co_authors(self):
        """The post owner should be able to list all co-authors."""
        from app.services.co_author import list_all_co_authors

        post_id = uuid.uuid4()
        owner_id = str(uuid.uuid4())

        post_row = {"id": post_id, "user_id": uuid.UUID(owner_id)}

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=post_row)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_COAUTHOR_SVC}.get_pool", return_value=mock_pool),
            patch(
                f"{_COAUTHOR_SVC}.co_author_repo.find_all_co_authors_by_post",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await list_all_co_authors(
                post_id=post_id, user_id=owner_id, is_admin=False
            )
            assert result == []

    @pytest.mark.anyio
    async def test_admin_can_list_all_co_authors(self):
        """An admin should be able to list all co-authors for any post."""
        from app.services.co_author import list_all_co_authors

        post_id = uuid.uuid4()
        owner_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())

        post_row = {"id": post_id, "user_id": uuid.UUID(owner_id)}

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=post_row)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_COAUTHOR_SVC}.get_pool", return_value=mock_pool),
            patch(
                f"{_COAUTHOR_SVC}.co_author_repo.find_all_co_authors_by_post",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await list_all_co_authors(
                post_id=post_id, user_id=admin_id, is_admin=True
            )
            assert result == []

    @pytest.mark.anyio
    async def test_nonexistent_post_returns_not_found(self):
        """Requesting co-authors for a nonexistent post should raise NotFoundError."""
        from app.core.errors import NotFoundError
        from app.services.co_author import list_all_co_authors

        post_id = uuid.uuid4()
        caller_id = str(uuid.uuid4())

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch(f"{_COAUTHOR_SVC}.get_pool", return_value=mock_pool):
            with pytest.raises(NotFoundError):
                await list_all_co_authors(
                    post_id=post_id, user_id=caller_id, is_admin=False
                )


# ── M-10: QA rate limiting ──────────────────────────────────────────────


class TestM10QaRateLimiting:
    """M-10: mark_best_answer and vote_on_answer should have rate limiting."""

    @pytest.mark.anyio
    async def test_mark_best_answer_rate_limited(self, client: AsyncClient):
        """When rate limit is exceeded, mark_best_answer returns 429."""
        _override_auth("MEMBER")
        try:
            with patch(
                f"{_QA_EP}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.post(
                    f"/api/v1/qa/{uuid.uuid4()}/best-answer",
                    json={"comment_id": str(uuid.uuid4())},
                )
            assert resp.status_code == 429
            assert resp.json()["detail"]["code"] == "SYS_429"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_vote_on_answer_rate_limited(self, client: AsyncClient):
        """When rate limit is exceeded, vote_on_answer returns 429."""
        _override_auth("MEMBER")
        try:
            with patch(
                f"{_QA_EP}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.post(
                    f"/api/v1/qa/comments/{uuid.uuid4()}/vote",
                    json={"vote": 1},
                )
            assert resp.status_code == 429
            assert resp.json()["detail"]["code"] == "SYS_429"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_mark_best_answer_passes_under_limit(self, client: AsyncClient):
        """When rate limit passes, endpoint proceeds to service layer."""
        uid = _override_auth("MEMBER")
        try:
            with (
                patch(
                    f"{_QA_EP}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_QA_EP}.mark_best_answer",
                    new_callable=AsyncMock,
                    return_value={"post_id": str(uuid.uuid4()), "best_answer_id": str(uuid.uuid4())},
                ),
            ):
                resp = await client.post(
                    f"/api/v1/qa/{uuid.uuid4()}/best-answer",
                    json={"comment_id": str(uuid.uuid4())},
                )
            assert resp.status_code == 200
        finally:
            _clear_overrides()


# ── M-38: Task ownership fail-closed ────────────────────────────────────


class TestM38TaskOwnershipFailClosed:
    """M-38: When Redis key is missing (TTL expired), MEMBER should get 403."""

    @pytest.mark.anyio
    async def test_member_gets_403_when_redis_key_expired(self, client: AsyncClient):
        """MEMBER user gets 403 when task_owner key has expired from Redis."""
        _override_auth("MEMBER")
        try:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)

            with patch(
                "app.core.redis.get_redis",
                return_value=mock_redis,
            ):
                resp = await client.get("/api/v1/tasks/some-task-id/status")
            assert resp.status_code == 403
            body = resp.json()
            assert body["detail"]["code"] == "SYS_403"
            assert "could not be verified" in body["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_member_gets_403_when_owner_mismatch(self, client: AsyncClient):
        """MEMBER user gets 403 when task belongs to a different user."""
        uid = _override_auth("MEMBER")
        try:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=str(uuid.uuid4()))  # different user

            with patch(
                "app.core.redis.get_redis",
                return_value=mock_redis,
            ):
                resp = await client.get("/api/v1/tasks/some-task-id/status")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_bypasses_ownership_check(self, client: AsyncClient):
        """ADMIN should not need ownership check — goes straight to Celery."""
        _override_auth("ADMIN")
        try:
            mock_result = MagicMock()
            mock_result.state = "PENDING"
            mock_result.result = None

            mock_celery = MagicMock()

            with (
                patch(
                    "celery.result.AsyncResult",
                    return_value=mock_result,
                ),
                patch("app.celery_app.celery", mock_celery),
            ):
                resp = await client.get("/api/v1/tasks/some-task-id/status")
            assert resp.status_code == 200
            assert resp.json()["status"] == "PENDING"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_member_can_access_own_task(self, client: AsyncClient):
        """MEMBER can access their own task when Redis key exists."""
        uid = _override_auth("MEMBER")
        try:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=uid)

            mock_result = MagicMock()
            mock_result.state = "SUCCESS"
            mock_result.result = {"download_url": "http://example.com/file.zip"}

            mock_celery = MagicMock()

            with (
                patch("app.core.redis.get_redis", return_value=mock_redis),
                patch(
                    "celery.result.AsyncResult",
                    return_value=mock_result,
                ),
                patch("app.celery_app.celery", mock_celery),
            ):
                resp = await client.get("/api/v1/tasks/some-task-id/status")
            assert resp.status_code == 200
            assert resp.json()["status"] == "SUCCESS"
        finally:
            _clear_overrides()


# ── L-05: File scan status ownership check ──────────────────────────────


class TestL05FileScanOwnership:
    """L-05: Only the uploader or admin should check scan status."""

    @pytest.mark.anyio
    async def test_non_owner_cannot_check_scan_status(self, client: AsyncClient):
        """A MEMBER who doesn't own the file gets 403."""
        uid = _override_auth("MEMBER")
        try:
            # Key belongs to a different user
            other_user = str(uuid.uuid4())
            key = f"editor/{other_user}/abc123.png"
            resp = await client.get(f"/api/v1/files/scan-status/{key}")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_owner_can_check_scan_status(self, client: AsyncClient):
        """The file uploader can check scan status."""
        uid = _override_auth("MEMBER")
        try:
            key = f"editor/{uid}/abc123.png"
            with patch(
                f"{_FILES_EP}.file_scan_repo.find_by_key",
                new_callable=AsyncMock,
                return_value={"status": "clean", "positives": 0, "total": 60},
            ):
                resp = await client.get(f"/api/v1/files/scan-status/{key}")
            assert resp.status_code == 200
            assert resp.json()["status"] == "clean"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_can_check_any_scan_status(self, client: AsyncClient):
        """An admin can check scan status for any file."""
        _override_auth("ADMIN")
        try:
            other_user = str(uuid.uuid4())
            key = f"editor/{other_user}/abc123.png"
            with patch(
                f"{_FILES_EP}.file_scan_repo.find_by_key",
                new_callable=AsyncMock,
                return_value={"status": "pending", "positives": None, "total": None},
            ):
                resp = await client.get(f"/api/v1/files/scan-status/{key}")
            assert resp.status_code == 200
            assert resp.json()["status"] == "pending"
        finally:
            _clear_overrides()


# ── L-06: about/members page upper bound ────────────────────────────────


class TestL06MembersPageUpperBound:
    """L-06: /about/members page param should have an upper bound."""

    @pytest.mark.anyio
    async def test_page_over_1000_rejected(self, client: AsyncClient):
        """page=1001 should be rejected by validation."""
        _override_auth("MEMBER")
        try:
            resp = await client.get("/api/v1/about/members?page=1001")
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_page_1000_accepted(self, client: AsyncClient):
        """page=1000 should be accepted."""
        _override_auth("MEMBER")
        try:
            with patch(
                "app.api.v1.endpoints.about.org_chart_service.get_members",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get("/api/v1/about/members?page=1000")
            assert resp.status_code == 200
        finally:
            _clear_overrides()


# ── L-07: Preferences/notifications block GUEST ─────────────────────────


class TestL07GuestBlockedFromPreferencesAndNotifications:
    """L-07: GUEST role should not be able to access preferences or notifications."""

    @pytest.mark.anyio
    async def test_guest_blocked_from_get_preferences(self, client: AsyncClient):
        _override_auth("GUEST")
        try:
            resp = await client.get("/api/v1/users/me/preferences")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_blocked_from_update_preferences(self, client: AsyncClient):
        _override_auth("GUEST")
        try:
            resp = await client.patch(
                "/api/v1/users/me/preferences",
                json={"dm_friends_only": True},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_blocked_from_get_notifications(self, client: AsyncClient):
        _override_auth("GUEST")
        try:
            resp = await client.get("/api/v1/notifications")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_blocked_from_mark_notification_read(self, client: AsyncClient):
        _override_auth("GUEST")
        try:
            resp = await client.put(f"/api/v1/notifications/{uuid.uuid4()}/read")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_blocked_from_read_all_notifications(self, client: AsyncClient):
        _override_auth("GUEST")
        try:
            resp = await client.put("/api/v1/notifications/read-all")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_blocked_from_delete_notification(self, client: AsyncClient):
        _override_auth("GUEST")
        try:
            resp = await client.delete(f"/api/v1/notifications/{uuid.uuid4()}")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


# ── L-08: Avatar upload blocks GUEST ────────────────────────────────────


class TestL08AvatarUploadBlocksGuest:
    """L-08: GUEST role should not be able to upload an avatar."""

    @pytest.mark.anyio
    async def test_guest_blocked_from_avatar_upload(self, client: AsyncClient):
        _override_auth("GUEST")
        try:
            resp = await client.put(
                "/api/v1/users/me/avatar",
                files={"file": ("avatar.png", b"fakepng", "image/png")},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_member_passes_role_check_for_avatar(self, client: AsyncClient):
        """MEMBER should pass the role check (service may error, but not 403)."""
        from app.core.errors import ServiceValidationError

        uid = _override_auth("MEMBER")
        try:
            # Raise a known service error after the role check passes
            with patch(
                "app.api.v1.endpoints.users.upload_user_avatar",
                new_callable=AsyncMock,
                side_effect=ServiceValidationError("Invalid image format"),
            ):
                resp = await client.put(
                    "/api/v1/users/me/avatar",
                    files={"file": ("avatar.png", b"fakepng", "image/png")},
                )
                # Should be 400 (validation error), NOT 403 (role block)
                assert resp.status_code == 400
        finally:
            _clear_overrides()


# ── L-09: Delete account blocks GUEST ───────────────────────────────────


class TestL09DeleteAccountBlocksGuest:
    """L-09: GUEST role should not be able to delete their account."""

    @pytest.mark.anyio
    async def test_guest_blocked_from_delete_account(self, client: AsyncClient):
        _override_auth("GUEST")
        try:
            resp = await client.delete("/api/v1/users/me")
            assert resp.status_code == 403
            body = resp.json()
            assert body["detail"]["code"] == "SYS_403"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_member_allowed_to_delete_account(self, client: AsyncClient):
        """MEMBER should pass the role check (proceeds to service layer)."""
        uid = _override_auth("MEMBER")
        try:
            with (
                patch(
                    "app.api.v1.endpoints.users.check_sole_admin_sigs",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
                patch(
                    "app.api.v1.endpoints.users.anonymize_user",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.api.v1.endpoints.users.revoke_user_sessions",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.users.emit",
                    new_callable=AsyncMock,
                ),
            ):
                resp = await client.delete("/api/v1/users/me")
            assert resp.status_code == 200
            assert "deleted" in resp.json()["message"].lower()
        finally:
            _clear_overrides()
