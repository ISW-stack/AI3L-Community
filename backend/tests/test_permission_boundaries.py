"""Tests for permission boundary enforcement across endpoints.

Covers: cross-SIG access prevention (forms, posts), regular member vs SIG admin,
MEMBER cannot assign sub-admin, comment deletion ownership, post-leave access,
and guest restrictions.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import _TEST_CSRF_TOKEN, _TEST_JWT_TOKEN

_SIG_A_ID = str(uuid.uuid4())
_SIG_B_ID = str(uuid.uuid4())
_USER_A_ID = str(uuid.uuid4())
_USER_B_ID = str(uuid.uuid4())
_FORM_B_ID = str(uuid.uuid4())
_POST_B_ID = str(uuid.uuid4())
_COMMENT_B_ID = str(uuid.uuid4())


@pytest.fixture
async def client():
    from app.main import app

    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"csrf_token": _TEST_CSRF_TOKEN},
            headers={
                "X-CSRF-Token": _TEST_CSRF_TOKEN,
                "Authorization": f"Bearer {_TEST_JWT_TOKEN}",
            },
        ) as ac:
            yield ac


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user, get_optional_current_user
    from app.main import app

    uid = user_id or _USER_A_ID
    payload = {"sub": uid, "role": role, "jti": "jti-perm"}
    app.dependency_overrides[get_current_user] = lambda: payload
    app.dependency_overrides[get_optional_current_user] = lambda: payload


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestCrossSIGFormAccess:
    """User from SIG A cannot access SIG B's forms."""

    @pytest.mark.anyio
    async def test_non_member_cannot_view_restricted_form(self, client: AsyncClient):
        """A user who is not a member of the form's SIG is denied access."""
        form_data = {
            "id": _FORM_B_ID,
            "sig_id": _SIG_B_ID,
            "title": "SIG B Form",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [],
            "response_count": 0,
            "created_by": _USER_B_ID,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }

        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.forms.get_form_by_id",
                    new_callable=AsyncMock,
                    return_value=form_data,
                ),
                patch(
                    "app.api.v1.endpoints.forms.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value=None,  # Not a member of SIG B
                ),
                patch(
                    "app.api.v1.endpoints.forms.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.get(f"/api/v1/forms/{_FORM_B_ID}")
            assert resp.status_code == 403
            assert "SIG members" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_non_member_cannot_view_form_responses(self, client: AsyncClient):
        """A regular member (not SIG admin) cannot view form responses."""
        form_data = {
            "id": _FORM_B_ID,
            "sig_id": _SIG_B_ID,
            "title": "SIG B Form",
            "created_by": _USER_B_ID,
            "allow_non_members": False,
        }

        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.forms.get_form_by_id",
                    new_callable=AsyncMock,
                    return_value=form_data,
                ),
                patch(
                    "app.api.v1.endpoints.forms.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value=None,  # Not a SIG admin
                ),
                patch(
                    "app.api.v1.endpoints.forms.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.get(f"/api/v1/forms/{_FORM_B_ID}/responses")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestCrossSIGPostEdit:
    """User from SIG A cannot edit SIG B's posts."""

    @pytest.mark.anyio
    async def test_non_owner_cannot_update_post(self, client: AsyncClient):
        """A user who did not author the post and is not admin is denied."""
        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.posts.update_post",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Not the author or admin."),
                ),
                patch(
                    "app.api.v1.endpoints.posts.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{_POST_B_ID}",
                    json={"title": "hacked", "content": "<p>hacked</p>", "version": 1},
                )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestRegularMemberCannotSIGAdmin:
    """Regular member cannot perform SIG admin operations."""

    @pytest.mark.anyio
    async def test_regular_member_cannot_create_form(self, client: AsyncClient):
        """A regular SIG member (not admin/sub-admin) cannot create forms."""
        _override_auth("MEMBER", _USER_A_ID)
        try:
            with patch(
                "app.dependencies.sig_admin.sig_repo.get_member_role",
                new_callable=AsyncMock,
                return_value="MEMBER",  # Just a regular member
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{_SIG_B_ID}/forms",
                    json={
                        "title": "Unauthorized Form",
                        "questions": [{"label": "Q1", "type": "text", "required": True}],
                    },
                )
            assert resp.status_code == 403
            assert "SIG admin" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_regular_member_cannot_update_others_form(self, client: AsyncClient):
        """A regular member cannot update a form they didn't create."""
        form_data = {
            "id": _FORM_B_ID,
            "sig_id": _SIG_B_ID,
            "title": "Some Form",
            "created_by": _USER_B_ID,  # Different user
            "allow_non_members": False,
        }

        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.forms.get_form_by_id",
                    new_callable=AsyncMock,
                    return_value=form_data,
                ),
                patch(
                    "app.api.v1.endpoints.forms.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",  # Not an admin
                ),
            ):
                resp = await client.put(
                    f"/api/v1/forms/{_FORM_B_ID}",
                    json={"title": "Updated Title"},
                )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestMemberCannotAssignSubAdmin:
    """MEMBER cannot assign sub-admin role."""

    @pytest.mark.anyio
    async def test_member_cannot_assign_sub_admin(self, client: AsyncClient):
        """A regular MEMBER cannot call assign_sub_admin (service raises PermissionError)."""
        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.sigs.assign_sub_admin",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Not authorized"),
                ),
                patch(
                    "app.api.v1.endpoints.sigs.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{_SIG_A_ID}/sub-admin",
                    json={"user_id": _USER_B_ID},
                )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestCommentDeletionOwnership:
    """User cannot delete another user's comment."""

    @pytest.mark.anyio
    async def test_non_owner_cannot_delete_comment(self, client: AsyncClient):
        """A non-owner, non-admin user cannot delete another user's comment."""
        post_id = str(uuid.uuid4())
        comment_id = str(uuid.uuid4())

        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.comments.soft_delete_comment",
                    new_callable=AsyncMock,
                    return_value=False,  # Service returns False = not authorized or not found
                ),
                patch(
                    "app.api.v1.endpoints.comments.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                )
            assert resp.status_code == 404
            assert "Comment not found" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_owner_can_delete_own_comment(self, client: AsyncClient):
        """The comment owner can delete their own comment."""
        post_id = str(uuid.uuid4())
        comment_id = str(uuid.uuid4())

        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.comments.soft_delete_comment",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.api.v1.endpoints.comments.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                )
            assert resp.status_code == 200
            assert "deleted" in resp.json()["message"].lower()
        finally:
            _clear_overrides()


class TestPostLeaveAccess:
    """After leaving a SIG, user cannot access SIG resources."""

    @pytest.mark.anyio
    async def test_non_member_cannot_submit_form(self, client: AsyncClient):
        """After leaving SIG, user cannot submit forms that require membership."""
        form_id = str(uuid.uuid4())

        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.forms.submit_response",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Only SIG members can submit"),
                ),
                patch(
                    "app.api.v1.endpoints.forms.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "answer1"}},
                )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_non_member_cannot_view_form_stats(self, client: AsyncClient):
        """After leaving, user cannot view form statistics."""
        form_id = str(uuid.uuid4())
        form_data = {
            "id": form_id,
            "sig_id": _SIG_B_ID,
            "title": "Form",
            "created_by": _USER_B_ID,
        }

        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.forms.get_form_by_id",
                    new_callable=AsyncMock,
                    return_value=form_data,
                ),
                patch(
                    "app.api.v1.endpoints.forms.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value=None,  # Not a member anymore
                ),
                patch(
                    "app.api.v1.endpoints.forms.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.get(f"/api/v1/forms/{form_id}/stats")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestGuestRestrictions:
    """Guest cannot access member-only endpoints."""

    @pytest.mark.anyio
    async def test_guest_cannot_create_post(self, client: AsyncClient):
        """GUEST role is blocked by require_role("SUPER_ADMIN", "ADMIN", "MEMBER")."""
        _override_auth("GUEST", _USER_A_ID)
        try:
            resp = await client.post(
                "/api/v1/posts",
                json={
                    "title": "Guest post",
                    "content": "<p>test</p>",
                },
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_cannot_create_sig(self, client: AsyncClient):
        """GUEST role cannot create SIGs (admin-only)."""
        _override_auth("GUEST", _USER_A_ID)
        try:
            resp = await client.post(
                "/api/v1/sigs",
                json={"name": "Guest SIG", "description": "test"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_cannot_join_sig(self, client: AsyncClient):
        """GUEST role cannot join SIGs."""
        sig_id = str(uuid.uuid4())
        _override_auth("GUEST", _USER_A_ID)
        try:
            resp = await client.post(f"/api/v1/sigs/{sig_id}/members/me")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_cannot_create_comment(self, client: AsyncClient):
        """GUEST role cannot create comments."""
        post_id = str(uuid.uuid4())
        _override_auth("GUEST", _USER_A_ID)
        try:
            resp = await client.post(
                f"/api/v1/posts/{post_id}/comments",
                json={"content": "<p>guest comment</p>"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_cannot_delete_post(self, client: AsyncClient):
        """GUEST role cannot delete posts."""
        post_id = str(uuid.uuid4())
        _override_auth("GUEST", _USER_A_ID)
        try:
            resp = await client.delete(f"/api/v1/posts/{post_id}")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_cannot_bulk_delete(self, client: AsyncClient):
        """GUEST role cannot use bulk delete (admin-only)."""
        _override_auth("GUEST", _USER_A_ID)
        try:
            resp = await client.request(
                "DELETE",
                "/api/v1/posts/bulk",
                json={"post_ids": [str(uuid.uuid4())]},
            )
            # bulk delete uses require_role("SUPER_ADMIN", "ADMIN") - guest should be denied
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestNonAdminCannotAdminOps:
    """Regular MEMBER cannot perform admin-level operations."""

    @pytest.mark.anyio
    async def test_member_cannot_delete_sig(self, client: AsyncClient):
        """MEMBER role cannot delete a SIG (admin-only)."""
        sig_id = str(uuid.uuid4())
        _override_auth("MEMBER", _USER_A_ID)
        try:
            resp = await client.delete(f"/api/v1/sigs/{sig_id}")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_member_cannot_pin_post(self, client: AsyncClient):
        """MEMBER role cannot pin posts (admin-only)."""
        post_id = str(uuid.uuid4())
        _override_auth("MEMBER", _USER_A_ID)
        try:
            resp = await client.patch(
                f"/api/v1/posts/{post_id}/pin",
                json={"is_pinned": True},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_member_cannot_export_form_for_other_sig(self, client: AsyncClient):
        """A non-SIG-admin MEMBER cannot export form CSV."""
        form_id = str(uuid.uuid4())
        form_data = {
            "id": form_id,
            "sig_id": _SIG_B_ID,
            "title": "Form",
            "created_by": _USER_B_ID,
        }

        _override_auth("MEMBER", _USER_A_ID)
        try:
            with (
                patch(
                    "app.api.v1.endpoints.forms.get_form_by_id",
                    new_callable=AsyncMock,
                    return_value=form_data,
                ),
                patch(
                    "app.api.v1.endpoints.forms.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value=None,  # Not a SIG admin
                ),
                patch(
                    "app.api.v1.endpoints.forms.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.post(f"/api/v1/forms/{form_id}/export")
            assert resp.status_code == 403
        finally:
            _clear_overrides()
