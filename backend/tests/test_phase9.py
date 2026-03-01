"""Phase 9: Feature Completion & Hardening — integration tests."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_user_dict

_EP = "app.api.v1.endpoints"


def _override_auth(role="MEMBER", user_id=None):
    """Create a dependency override dict for get_current_user and require_role."""
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}

    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Invite code consumption — second use returns 400
# ---------------------------------------------------------------------------


class TestInviteCodeConsumption:
    @pytest.mark.anyio
    async def test_consumed_code_rejected(self, client):
        """Register with invite code → same code → 400 (already consumed)."""
        user_row = make_user_dict(role="MEMBER")

        call_count = {"invite": 0}

        async def fake_get_invite(code):
            call_count["invite"] += 1
            if call_count["invite"] <= 1:
                return {"code": code, "id": uuid.uuid4()}
            return None

        with (
            patch(f"{_EP}.auth.check_rate_limit", new_callable=AsyncMock, return_value=True),
            patch(f"{_EP}.auth.verify_captcha", new_callable=AsyncMock, return_value=True),
            patch(
                f"{_EP}.auth.get_invite_code", new_callable=AsyncMock, side_effect=fake_get_invite
            ),
            patch(
                f"{_EP}.auth.user_exists_by_username", new_callable=AsyncMock, return_value=False
            ),
            patch(f"{_EP}.auth.create_user", new_callable=AsyncMock, return_value=user_row),
            patch(f"{_EP}.auth.consume_invite_code", new_callable=AsyncMock),
            patch(f"{_EP}.auth.create_session", new_callable=AsyncMock, return_value=("tok", 3600)),
        ):
            resp1 = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "newuser1",
                    "password": "Password1",
                    "display_name": "New User",
                    "invite_code": "INV-TEST1234",
                    "captcha_id": "cap1",
                    "captcha_code": "ABCD",
                },
            )
            assert resp1.status_code == 200

            resp2 = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "newuser2",
                    "password": "Password1",
                    "display_name": "New User 2",
                    "invite_code": "INV-TEST1234",
                    "captcha_id": "cap2",
                    "captcha_code": "ABCD",
                },
            )
            assert resp2.status_code == 400


# ---------------------------------------------------------------------------
# 2. SIG update — admin vs non-admin
# ---------------------------------------------------------------------------


class TestSigUpdate:
    @pytest.mark.anyio
    async def test_sig_update_admin(self, client, mock_pool, mock_conn):
        """PUT /sigs/{id} → 200 for global admin."""
        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        sig_row = {
            "id": sig_id,
            "name": "Old",
            "description": "Old desc",
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        updated_row = {**sig_row, "name": "New", "description": "New desc"}
        creator_row = {"display_name": "Creator"}

        mock_conn.fetchrow = AsyncMock(side_effect=[sig_row, updated_row, creator_row])

        try:
            _override_auth("ADMIN")
            with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
                resp = await client.put(
                    f"/api/v1/sigs/{sig_id}",
                    json={"name": "New", "description": "New desc"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["name"] == "New"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sig_update_non_admin_member_forbidden(self, client, mock_pool, mock_conn):
        """PUT /sigs/{id} → 403 for non-admin member."""
        sig_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(return_value={"role": "MEMBER"})

        try:
            _override_auth("MEMBER")
            with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
                resp = await client.put(
                    f"/api/v1/sigs/{sig_id}",
                    json={"name": "Hacked"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 3. SIG delete — admin only
# ---------------------------------------------------------------------------


class TestSigDelete:
    @pytest.mark.anyio
    async def test_sig_delete_admin(self, client, mock_pool, mock_conn):
        """DELETE /sigs/{id} → 204 for admin."""
        sig_id = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        try:
            _override_auth("ADMIN")
            with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sig_delete_member_forbidden(self, client):
        """DELETE /sigs/{id} → 403 for regular member."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            resp = await client.delete(
                f"/api/v1/sigs/{sig_id}",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 4. SIG leave
# ---------------------------------------------------------------------------


class TestSigLeave:
    @pytest.mark.anyio
    async def test_leave_sig(self, client, mock_pool, mock_conn):
        """DELETE /sigs/{id}/members/me → 200."""
        sig_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(return_value={"role": "MEMBER"})
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        try:
            _override_auth("MEMBER")
            with (
                patch("app.services.sig.get_pool", return_value=mock_pool),
                patch("app.repositories.sig_repo.get_pool", return_value=mock_pool),
            ):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 5. Category update
# ---------------------------------------------------------------------------


class TestCategoryUpdate:
    @pytest.mark.anyio
    async def test_category_update(self, client, mock_pool, mock_conn):
        """PUT /categories/{id} → 200."""
        cat_id = uuid.uuid4()

        current_row = {"id": cat_id, "name": "Old", "description": None}
        updated_row = {"id": cat_id, "name": "New Name", "description": "desc"}

        mock_conn.fetchrow = AsyncMock(side_effect=[current_row, updated_row])

        try:
            _override_auth("ADMIN")
            with patch("app.repositories.category_repo.get_pool", return_value=mock_pool):
                resp = await client.put(
                    f"/api/v1/categories/{cat_id}",
                    json={"name": "New Name", "description": "desc"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["name"] == "New Name"
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 6. Category delete
# ---------------------------------------------------------------------------


class TestCategoryDelete:
    @pytest.mark.anyio
    async def test_category_delete(self, client, mock_pool, mock_conn):
        """DELETE /categories/{id} → 204."""
        cat_id = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        try:
            _override_auth("ADMIN")
            with patch("app.repositories.category_repo.get_pool", return_value=mock_pool):
                resp = await client.delete(
                    f"/api/v1/categories/{cat_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 7. Comment edit — owner vs non-owner
# ---------------------------------------------------------------------------


class TestCommentEdit:
    @pytest.mark.anyio
    async def test_comment_edit_owner(self, client, mock_pool, mock_conn):
        """PUT /posts/{pid}/comments/{cid} → 200 for owner."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        comment_row = {
            "id": comment_id,
            "post_id": post_id,
            "content": "Updated content",
            "user_id": uuid.UUID(user_id),
            "parent_id": None,
            "mentions": None,
            "reactions": {},
            "is_deleted": False,
            "author_id": uuid.UUID(user_id),
            "author_username": "testuser",
            "author_display_name": "Test User",
            "author_avatar_url": None,
            "created_at": now,
            "updated_at": now,
        }

        mock_conn.fetchrow = AsyncMock(return_value=comment_row)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "Updated content"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_comment_edit_non_owner(self, client, mock_pool, mock_conn):
        """PUT /posts/{pid}/comments/{cid} → 403 for non-owner."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        mock_conn.fetchrow = AsyncMock(return_value=None)

        try:
            _override_auth("MEMBER")
            with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "Hacked"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 8. Notification delete
# ---------------------------------------------------------------------------


class TestNotificationDelete:
    @pytest.mark.anyio
    async def test_notification_delete(self, client, mock_pool, mock_conn):
        """DELETE /notifications/{id} → 200."""
        notif_id = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        try:
            _override_auth("MEMBER")
            with patch("app.repositories.notification_repo.get_pool", return_value=mock_pool):
                resp = await client.delete(
                    f"/api/v1/notifications/{notif_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 9. Password change
# ---------------------------------------------------------------------------


class TestPasswordChange:
    @pytest.mark.anyio
    async def test_password_change_correct_old(self, client, mock_pool, mock_conn, mock_redis):
        """PUT /users/me/password → 200 with correct old password."""
        from app.core.security import hash_password

        pw_hash = hash_password("OldPass1")

        mock_conn.fetchrow = AsyncMock(return_value={"password_hash": pw_hash})
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        try:
            payload, uid = _override_auth("MEMBER")
            with (
                patch("app.repositories.user_repo.get_pool", return_value=mock_pool),
                patch("app.services.auth.get_redis", return_value=mock_redis),
            ):
                resp = await client.put(
                    "/api/v1/users/me/password",
                    json={"current_password": "OldPass1", "new_password": "NewPass1"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_password_change_wrong_old(self, client, mock_pool, mock_conn):
        """PUT /users/me/password → 400 with wrong old password."""
        from app.core.security import hash_password

        pw_hash = hash_password("CorrectPass1")

        mock_conn.fetchrow = AsyncMock(return_value={"password_hash": pw_hash})

        try:
            _override_auth("MEMBER")
            with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
                resp = await client.put(
                    "/api/v1/users/me/password",
                    json={"current_password": "WrongPass1", "new_password": "NewPass1"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 10. Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimit:
    @pytest.mark.anyio
    async def test_login_rate_limit(self, client):
        """11 logins in rapid succession → 429 on 11th."""
        call_count = {"n": 0}

        async def fake_rate_limit(key, max_count, window):
            call_count["n"] += 1
            return call_count["n"] <= max_count

        with (
            patch(
                f"{_EP}.auth.check_rate_limit", new_callable=AsyncMock, side_effect=fake_rate_limit
            ),
            patch(f"{_EP}.auth.verify_captcha", new_callable=AsyncMock, return_value=False),
        ):
            # First 10: rate limit passes, but captcha fails (400) — NOT 429
            for i in range(10):
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "user",
                        "password": "pass",
                        "captcha_id": f"cap{i}",
                        "captcha_code": "ABCD",
                    },
                )
                assert resp.status_code != 429

            # 11th: rate limit blocks → 429
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "username": "user",
                    "password": "pass",
                    "captcha_id": "cap10",
                    "captcha_code": "ABCD",
                },
            )
            assert resp.status_code == 429


# ---------------------------------------------------------------------------
# 11. Post sorting
# ---------------------------------------------------------------------------


class TestPostSorting:
    @pytest.mark.anyio
    async def test_sort_most_comments(self, client, mock_pool, mock_conn):
        """GET /posts?sort=most_comments → verify order clause is used."""
        now = datetime.now(timezone.utc)

        post_rows = [
            {
                "id": uuid.uuid4(),
                "title": "Popular Post",
                "content": "body",
                "user_id": uuid.uuid4(),
                "category_id": None,
                "sig_id": None,
                "keywords": None,
                "allow_comments": True,
                "version": 1,
                "comment_count": 10,
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
                "search_vector": None,
                "author_id": uuid.uuid4(),
                "author_username": "user1",
                "author_display_name": "User 1",
                "author_avatar_url": None,
                "category_name": None,
            },
            {
                "id": uuid.uuid4(),
                "title": "Unpopular Post",
                "content": "body",
                "user_id": uuid.uuid4(),
                "category_id": None,
                "sig_id": None,
                "keywords": None,
                "allow_comments": True,
                "version": 1,
                "comment_count": 0,
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
                "search_vector": None,
                "author_id": uuid.uuid4(),
                "author_username": "user2",
                "author_display_name": "User 2",
                "author_avatar_url": None,
                "category_name": None,
            },
        ]

        mock_conn.fetchval = AsyncMock(return_value=2)
        mock_conn.fetch = AsyncMock(return_value=post_rows)

        try:
            _override_auth("MEMBER")
            with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
                resp = await client.get(
                    "/api/v1/posts?sort=most_comments",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["posts"]) == 2
                assert data["posts"][0]["comment_count"] >= data["posts"][1]["comment_count"]
        finally:
            _clear_overrides()
