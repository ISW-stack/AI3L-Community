"""Tests for org chart and members endpoints."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.about"
_SVC = "app.services.org_chart"
_SIG_REPO = "app.repositories.sig_repo"

_SIG_ID = uuid.uuid4()
_CAT_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()

_FAKE_SIG = {
    "id": str(_SIG_ID),
    "name": "AI & NLP",
    "description": "Natural language processing SIG",
    "org_chart_description": None,
    "member_count": 3,
    "members": [
        {
            "user_id": str(_USER_ID),
            "display_name": "Alice",
            "username": "alice",
            "avatar_url": None,
            "role": "ADMIN",
            "org_chart_bio": None,
        }
    ],
    "override": None,
}

_FAKE_SIG_HIDDEN = {
    **_FAKE_SIG,
    "id": str(uuid.uuid4()),
    "name": "Hidden SIG",
    "override": {
        "entity_type": "sig",
        "entity_id": str(uuid.uuid4()),
        "custom_title": None,
        "custom_description": None,
        "display_order": 0,
        "is_visible": False,
    },
}

_FAKE_CAT = {
    "id": str(_CAT_ID),
    "name": "General",
    "description": None,
    "creator_id": str(_USER_ID),
    "creator_display_name": "Alice",
    "creator_avatar_url": None,
    "override": None,
}

_FULL_ORG_CHART = {
    "sigs": [_FAKE_SIG, _FAKE_SIG_HIDDEN],
    "categories": [_FAKE_CAT],
}

_FAKE_MEMBER = {
    "id": str(_USER_ID),
    "username": "alice",
    "display_name": "Alice",
    "avatar_url": None,
    "role": "MEMBER",
    "affiliation": "NTNU",
    "bio": "Researcher",
}


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


# ── GET /about/org-chart ────────────────────────────────────────────────


class TestGetOrgChart:
    @pytest.mark.anyio
    async def test_member_sees_visible_only(self, client):
        """MEMBER gets org chart with hidden entries filtered out."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SVC}.get_org_chart", new_callable=AsyncMock) as mock_get:
                # Service returns only visible sigs for non-super-admin
                mock_get.return_value = {"sigs": [_FAKE_SIG], "categories": [_FAKE_CAT]}
                resp = await client.get("/api/v1/about/org-chart")

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["sigs"]) == 1
            assert data["sigs"][0]["name"] == "AI & NLP"
            # Verify service called with is_super_admin=False
            mock_get.assert_called_once_with(is_super_admin=False)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_super_admin_sees_hidden(self, client):
        """SUPER_ADMIN gets all entries including hidden."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(f"{_SVC}.get_org_chart", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = _FULL_ORG_CHART
                resp = await client.get("/api/v1/about/org-chart")

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["sigs"]) == 2
            mock_get.assert_called_once_with(is_super_admin=True)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_blocked(self, client):
        """GUEST cannot access org chart."""
        try:
            _override_auth("GUEST")
            with patch(f"{_SVC}.get_org_chart", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"sigs": [], "categories": []}
                resp = await client.get("/api/v1/about/org-chart")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_unauthenticated_blocked(self, client):
        """Unauthenticated requests are rejected."""
        resp = await client.get("/api/v1/about/org-chart")
        assert resp.status_code in (401, 403)


# ── GET /about/members ──────────────────────────────────────────────────


class TestGetMembers:
    @pytest.mark.anyio
    async def test_member_can_list(self, client):
        """MEMBER gets paginated member list."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SVC}.get_members", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = ([_FAKE_MEMBER], 1)
                resp = await client.get("/api/v1/about/members")

            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["members"][0]["display_name"] == "Alice"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_pagination_params_forwarded(self, client):
        """Pagination and search params are forwarded to service."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SVC}.get_members", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = ([], 0)
                resp = await client.get("/api/v1/about/members?page=2&page_size=10&search=alice")

            assert resp.status_code == 200
            # offset = (2-1)*10 = 10
            mock_get.assert_called_once_with(offset=10, limit=10, search="alice")
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_empty_search_treated_as_none(self, client):
        """Empty search string is forwarded as None."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SVC}.get_members", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = ([], 0)
                await client.get("/api/v1/about/members?search=")

            mock_get.assert_called_once_with(offset=0, limit=24, search=None)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_blocked(self, client):
        """GUEST cannot list members."""
        try:
            _override_auth("GUEST")
            resp = await client.get("/api/v1/about/members")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


# ── PUT /about/org-chart/override/:type/:id ─────────────────────────────


class TestUpdateOverride:
    @pytest.mark.anyio
    async def test_super_admin_can_update(self, client):
        """SUPER_ADMIN can update an override."""
        try:
            _override_auth("SUPER_ADMIN")
            fake_result = {
                "entity_type": "sig",
                "entity_id": _SIG_ID,
                "custom_title": "Renamed SIG",
                "custom_description": None,
                "display_order": 1,
                "is_visible": True,
            }
            with patch(f"{_SVC}.update_override", new_callable=AsyncMock) as mock_update:
                mock_update.return_value = fake_result
                resp = await client.put(
                    f"/api/v1/about/org-chart/override/sig/{_SIG_ID}",
                    json={"custom_title": "Renamed SIG", "display_order": 1},
                )

            assert resp.status_code == 200
            assert resp.json()["custom_title"] == "Renamed SIG"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_member_cannot_update(self, client):
        """MEMBER cannot update overrides."""
        try:
            _override_auth("MEMBER")
            resp = await client.put(
                f"/api/v1/about/org-chart/override/sig/{_SIG_ID}",
                json={"is_visible": False},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_invalid_entity_type_rejected(self, client):
        """Invalid entity_type returns 422."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(f"{_SVC}.update_override", new_callable=AsyncMock):
                resp = await client.put(
                    f"/api/v1/about/org-chart/override/invalid/{_SIG_ID}",
                    json={"is_visible": False},
                )
            assert resp.status_code == 422
        finally:
            _clear_overrides()


# ── PUT /about/org-chart/sigs/:id/description ───────────────────────────


class TestUpdateSigDescription:
    @pytest.mark.anyio
    async def test_sig_admin_can_update(self, client):
        """SIG ADMIN can update org chart description."""
        try:
            payload, uid = _override_auth("MEMBER")
            with patch(f"{_SIG_REPO}.get_member_role", new_callable=AsyncMock) as mock_role, \
                 patch(f"{_SVC}.update_sig_description", new_callable=AsyncMock) as mock_update:
                mock_role.return_value = "ADMIN"
                mock_update.return_value = True
                resp = await client.put(
                    f"/api/v1/about/org-chart/sigs/{_SIG_ID}/description",
                    json={"org_chart_description": "Our SIG focuses on NLP research."},
                )

            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sub_admin_can_update(self, client):
        """SIG SUB_ADMIN can update org chart description."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SIG_REPO}.get_member_role", new_callable=AsyncMock) as mock_role, \
                 patch(f"{_SVC}.update_sig_description", new_callable=AsyncMock) as mock_update:
                mock_role.return_value = "SUB_ADMIN"
                mock_update.return_value = True
                resp = await client.put(
                    f"/api/v1/about/org-chart/sigs/{_SIG_ID}/description",
                    json={"org_chart_description": "Updated description."},
                )

            assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_plain_member_cannot_update(self, client):
        """Plain MEMBER (not SIG admin) gets 403."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SIG_REPO}.get_member_role", new_callable=AsyncMock) as mock_role:
                mock_role.return_value = "MEMBER"
                resp = await client.put(
                    f"/api/v1/about/org-chart/sigs/{_SIG_ID}/description",
                    json={"org_chart_description": "Trying to update."},
                )

            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_super_admin_bypasses_sig_role_check(self, client):
        """SUPER_ADMIN can update any SIG description without being a member."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(f"{_SVC}.update_sig_description", new_callable=AsyncMock) as mock_update:
                mock_update.return_value = True
                resp = await client.put(
                    f"/api/v1/about/org-chart/sigs/{_SIG_ID}/description",
                    json={"org_chart_description": "Super admin update."},
                )

            assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sig_not_found_returns_404(self, client):
        """Returns 404 when SIG update returns False."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(f"{_SVC}.update_sig_description", new_callable=AsyncMock) as mock_update:
                mock_update.return_value = False
                resp = await client.put(
                    f"/api/v1/about/org-chart/sigs/{_SIG_ID}/description",
                    json={"org_chart_description": "x"},
                )

            assert resp.status_code == 404
        finally:
            _clear_overrides()


# ── PUT /about/org-chart/sigs/:id/members/me/bio ────────────────────────


class TestUpdateMemberBio:
    @pytest.mark.anyio
    async def test_member_can_update_own_bio(self, client):
        """SIG member can update their own org chart bio."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SIG_REPO}.get_member_role", new_callable=AsyncMock) as mock_role, \
                 patch(f"{_SVC}.update_member_bio", new_callable=AsyncMock) as mock_update:
                mock_role.return_value = "MEMBER"
                mock_update.return_value = True
                resp = await client.put(
                    f"/api/v1/about/org-chart/sigs/{_SIG_ID}/members/me/bio",
                    json={"org_chart_bio": "I research NLP."},
                )

            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_non_member_cannot_update_bio(self, client):
        """Non-member of a SIG gets 403 when updating bio."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SIG_REPO}.get_member_role", new_callable=AsyncMock) as mock_role:
                mock_role.return_value = None  # not a member
                resp = await client.put(
                    f"/api/v1/about/org-chart/sigs/{_SIG_ID}/members/me/bio",
                    json={"org_chart_bio": "I research NLP."},
                )

            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_bio_not_found_returns_404(self, client):
        """Returns 404 when membership record not found by update."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SIG_REPO}.get_member_role", new_callable=AsyncMock) as mock_role, \
                 patch(f"{_SVC}.update_member_bio", new_callable=AsyncMock) as mock_update:
                mock_role.return_value = "MEMBER"
                mock_update.return_value = False
                resp = await client.put(
                    f"/api/v1/about/org-chart/sigs/{_SIG_ID}/members/me/bio",
                    json={"org_chart_bio": "Hello."},
                )

            assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_can_clear_bio(self, client):
        """Passing null bio clears the field."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_SIG_REPO}.get_member_role", new_callable=AsyncMock) as mock_role, \
                 patch(f"{_SVC}.update_member_bio", new_callable=AsyncMock) as mock_update:
                mock_role.return_value = "ADMIN"
                mock_update.return_value = True
                resp = await client.put(
                    f"/api/v1/about/org-chart/sigs/{_SIG_ID}/members/me/bio",
                    json={"org_chart_bio": None},
                )

            assert resp.status_code == 200
        finally:
            _clear_overrides()
