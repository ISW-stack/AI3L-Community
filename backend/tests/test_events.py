"""Tests for the Events feature.

Covers: schemas, repository, service, and endpoint layers.
"""

import math
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError, ErrorCode

_REPO = "app.repositories.event_repo"
_SVC = "app.services.event"
_COMMENT_SVC = "app.services.comment"
_EP = "app.api.v1.endpoints.events"

_NOW = datetime.now(timezone.utc)
_USER_ID = str(uuid.uuid4())
_EVENT_ID = uuid.uuid4()


def _override_auth(role="ADMIN", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


def _make_event_row(
    event_id=None,
    user_id=None,
    title="Test Event",
    content="<p>Hello</p>",
    sig_id=None,
    visibility=None,
    allow_comments=True,
    comment_count=0,
    version=1,
):
    uid = uuid.UUID(user_id) if user_id else uuid.uuid4()
    return {
        "id": event_id or uuid.uuid4(),
        "user_id": uid,
        "title": title,
        "content": content,
        "sig_id": sig_id,
        "visibility": visibility or ["MEMBER"],
        "allow_comments": allow_comments,
        "comment_count": comment_count,
        "reactions": None,
        "version": version,
        "is_deleted": False,
        "created_at": _NOW,
        "updated_at": _NOW,
        "author_id": uid,
        "author_username": "testadmin",
        "author_display_name": "Test Admin",
        "author_avatar_url": None,
        "sig_name": None,
    }


# ── Schema Tests ──


class TestEventSchemas:
    def test_create_request_valid(self):
        from app.schemas.event import EventCreateRequest

        req = EventCreateRequest(
            title="Event 1",
            content="<p>Hello</p>",
            visibility=["GUEST", "MEMBER"],
        )
        assert req.title == "Event 1"
        assert sorted(req.visibility) == ["GUEST", "MEMBER"]

    def test_create_request_invalid_visibility(self):
        from app.schemas.event import EventCreateRequest

        with pytest.raises(Exception):
            EventCreateRequest(
                title="Event 1",
                content="<p>Hello</p>",
                visibility=["INVALID_ROLE"],
            )

    def test_create_request_empty_visibility_rejected(self):
        from app.schemas.event import EventCreateRequest

        with pytest.raises(Exception):
            EventCreateRequest(
                title="Event 1",
                content="<p>Hello</p>",
                visibility=[],
            )

    def test_create_request_deduplicates_visibility(self):
        from app.schemas.event import EventCreateRequest

        req = EventCreateRequest(
            title="Test",
            content="<p>Hi</p>",
            visibility=["MEMBER", "MEMBER", "GUEST"],
        )
        assert req.visibility == ["GUEST", "MEMBER"]

    def test_update_request_requires_version(self):
        from app.schemas.event import EventUpdateRequest

        with pytest.raises(Exception):
            EventUpdateRequest(title="Updated")

    def test_update_request_valid(self):
        from app.schemas.event import EventUpdateRequest

        req = EventUpdateRequest(title="Updated", version=1)
        assert req.title == "Updated"
        assert req.version == 1

    def test_event_response_model(self):
        from app.schemas.event import EventResponse

        resp = EventResponse(
            id=str(uuid.uuid4()),
            title="Event",
            content="<p>Hi</p>",
            author={"id": "1", "username": "u", "display_name": "U", "avatar_url": None},
            visibility=["MEMBER"],
            allow_comments=True,
            created_at="2026-03-31T00:00:00",
            updated_at="2026-03-31T00:00:00",
        )
        assert resp.title == "Event"


# ── Converter Tests ──


class TestEventConverter:
    @pytest.mark.asyncio
    async def test_async_row_to_event(self):
        from app.converters.event_converter import async_row_to_event

        row = _make_event_row()
        with patch("app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None):
            result = await async_row_to_event(row)
        assert result["title"] == "Test Event"
        assert result["visibility"] == ["MEMBER"]
        assert isinstance(result["created_at"], str)

    def test_sync_row_to_event(self):
        from app.converters.event_converter import row_to_event

        row = _make_event_row()
        with patch("app.converters.shared.resolve_avatar_url", return_value=None):
            result = row_to_event(row)
        assert result["title"] == "Test Event"
        assert result["version"] == 1


# ── Repository Tests ──


class TestEventRepo:
    @pytest.mark.asyncio
    async def test_insert(self, mock_pool, mock_conn):
        row = _make_event_row()
        mock_conn.fetchrow = AsyncMock(return_value=row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.event_repo import insert

            result = await insert(
                event_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                title="Test",
                content="<p>Hi</p>",
                sig_id=None,
                visibility=["MEMBER"],
                allow_comments=True,
            )
        assert result["title"] == "Test Event"
        mock_conn.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_find_by_id_no_role_filter(self, mock_pool, mock_conn):
        row = _make_event_row()
        mock_conn.fetchrow = AsyncMock(return_value=row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.event_repo import find_by_id

            result = await find_by_id(uuid.uuid4(), user_role="SUPER_ADMIN")
        assert result is not None
        # SUPER_ADMIN should not have visibility filter
        call_sql = mock_conn.fetchrow.call_args[0][0]
        assert "visibility" not in call_sql

    @pytest.mark.asyncio
    async def test_find_by_id_with_role_filter(self, mock_pool, mock_conn):
        row = _make_event_row()
        mock_conn.fetchrow = AsyncMock(return_value=row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.event_repo import find_by_id

            await find_by_id(uuid.uuid4(), user_role="MEMBER")
        call_sql = mock_conn.fetchrow.call_args[0][0]
        assert "visibility" in call_sql

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, mock_pool, mock_conn):
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.event_repo import find_by_id

            result = await find_by_id(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_find_many(self, mock_pool, mock_conn):
        row = _make_event_row()
        row["_total"] = 1
        mock_conn.fetch = AsyncMock(return_value=[row])

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.event_repo import find_many

            result = await find_many(page=1, page_size=20, user_role="MEMBER")
        assert result["total"] == 1
        assert len(result["events"]) == 1

    @pytest.mark.asyncio
    async def test_find_many_empty(self, mock_pool, mock_conn):
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.event_repo import find_many

            result = await find_many(page=1, page_size=20)
        assert result["total"] == 0
        assert result["events"] == []

    @pytest.mark.asyncio
    async def test_soft_delete(self, mock_pool, mock_conn):
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.event_repo import soft_delete

            result = await soft_delete(uuid.uuid4())
        assert result is True

    @pytest.mark.asyncio
    async def test_soft_delete_not_found(self, mock_pool, mock_conn):
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.event_repo import soft_delete

            result = await soft_delete(uuid.uuid4())
        assert result is False


# ── Service Tests ──


class TestEventService:
    @pytest.mark.asyncio
    async def test_create_event_success(self):
        row = _make_event_row(user_id=_USER_ID)
        with (
            patch(f"{_SVC}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            patch(f"{_SVC}.event_repo.insert", new_callable=AsyncMock, return_value=row),
            patch(f"{_SVC}.emit", new_callable=AsyncMock),
            patch("app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None),
        ):
            from app.services.event import create_event

            result = await create_event(
                user_id=_USER_ID,
                title="Test",
                content="<p>Hi</p>",
                visibility=["MEMBER"],
            )
        assert result["title"] == "Test Event"

    @pytest.mark.asyncio
    async def test_create_event_rate_limited(self):
        with patch(f"{_SVC}.check_rate_limit", new_callable=AsyncMock, return_value=False):
            from app.core.errors import RateLimitError
            from app.services.event import create_event

            with pytest.raises(RateLimitError):
                await create_event(
                    user_id=_USER_ID,
                    title="Test",
                    content="<p>Hi</p>",
                    visibility=["MEMBER"],
                )

    @pytest.mark.asyncio
    async def test_create_event_no_visibility(self):
        from app.services.event import create_event

        with pytest.raises(ValueError, match="Visibility must include"):
            await create_event(
                user_id=_USER_ID,
                title="Test",
                content="<p>Hi</p>",
                visibility=None,
            )

    @pytest.mark.asyncio
    async def test_get_event(self):
        row = _make_event_row()
        with (
            patch(f"{_SVC}.event_repo.find_by_id", new_callable=AsyncMock, return_value=row),
            patch("app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None),
        ):
            from app.services.event import get_event

            result = await get_event(uuid.uuid4(), user_role="MEMBER")
        assert result is not None
        assert result["title"] == "Test Event"

    @pytest.mark.asyncio
    async def test_get_event_not_found(self):
        with patch(f"{_SVC}.event_repo.find_by_id", new_callable=AsyncMock, return_value=None):
            from app.services.event import get_event

            result = await get_event(uuid.uuid4(), user_role="MEMBER")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_event_permission_denied(self):
        other_user = str(uuid.uuid4())
        row = _make_event_row(user_id=_USER_ID)
        with patch(f"{_SVC}.event_repo.find_by_id", new_callable=AsyncMock, return_value=row):
            from app.services.event import delete_event

            with pytest.raises(PermissionError):
                await delete_event(uuid.uuid4(), user_id=other_user, caller_role="ADMIN")

    @pytest.mark.asyncio
    async def test_delete_event_super_admin_bypass(self):
        other_user = str(uuid.uuid4())
        row = _make_event_row(user_id=_USER_ID)
        with (
            patch(f"{_SVC}.event_repo.find_by_id", new_callable=AsyncMock, return_value=row),
            patch(f"{_SVC}.event_repo.soft_delete", new_callable=AsyncMock, return_value=True),
            patch(f"{_SVC}.emit", new_callable=AsyncMock),
        ):
            from app.services.event import delete_event

            result = await delete_event(uuid.uuid4(), user_id=other_user, caller_role="SUPER_ADMIN")
        assert result is True

    @pytest.mark.asyncio
    async def test_update_event_permission_denied(self):
        other_user = str(uuid.uuid4())
        row = _make_event_row(user_id=_USER_ID)
        with patch(f"{_SVC}.event_repo.find_by_id", new_callable=AsyncMock, return_value=row):
            from app.services.event import update_event

            with pytest.raises(PermissionError):
                await update_event(
                    uuid.uuid4(),
                    user_id=other_user,
                    caller_role="ADMIN",
                    title="New",
                    expected_version=1,
                )

    @pytest.mark.asyncio
    async def test_list_events(self):
        row = _make_event_row()
        data = {"events": [row], "total": 1}
        with (
            patch(f"{_SVC}.event_repo.find_many", new_callable=AsyncMock, return_value=data),
            patch("app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None),
        ):
            from app.services.event import list_events

            result = await list_events(page=1, page_size=20, user_role="MEMBER")
        assert result["total"] == 1
        assert len(result["events"]) == 1


# ── Endpoint Tests ──


class TestEventEndpoints:
    @pytest.mark.asyncio
    async def test_create_event_requires_admin(self, client):
        _override_auth(role="MEMBER")
        try:
            resp = await client.post(
                "/api/v1/events",
                json={
                    "title": "Test",
                    "content": "<p>Hi</p>",
                    "visibility": ["MEMBER"],
                },
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.asyncio
    async def test_create_event_success(self, client):
        payload, uid = _override_auth(role="ADMIN")
        row = _make_event_row(user_id=uid)

        with (
            patch(f"{_SVC}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            patch(f"{_SVC}.event_repo.insert", new_callable=AsyncMock, return_value=row),
            patch(f"{_SVC}.emit", new_callable=AsyncMock),
            patch("app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None),
        ):
            try:
                resp = await client.post(
                    "/api/v1/events",
                    json={
                        "title": "Test Event",
                        "content": "<p>Hello</p>",
                        "visibility": ["MEMBER"],
                    },
                )
                assert resp.status_code == 201
                data = resp.json()
                assert data["title"] == "Test Event"
            finally:
                _clear_overrides()

    @pytest.mark.asyncio
    async def test_list_events(self, client):
        payload, uid = _override_auth(role="MEMBER")
        row = _make_event_row()
        row["_total"] = 1
        find_data = {"events": [row], "total": 1}

        with (
            patch(f"{_SVC}.event_repo.find_many", new_callable=AsyncMock, return_value=find_data),
            patch("app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None),
        ):
            try:
                resp = await client.get("/api/v1/events")
                assert resp.status_code == 200
                data = resp.json()
                assert "events" in data
                assert data["total"] == 1
            finally:
                _clear_overrides()

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, client):
        _override_auth(role="MEMBER")
        with patch(f"{_SVC}.event_repo.find_by_id", new_callable=AsyncMock, return_value=None):
            try:
                resp = await client.get(f"/api/v1/events/{uuid.uuid4()}")
                assert resp.status_code == 404
            finally:
                _clear_overrides()

    @pytest.mark.asyncio
    async def test_get_event_success(self, client):
        payload, uid = _override_auth(role="MEMBER")
        row = _make_event_row()

        with (
            patch(f"{_SVC}.event_repo.find_by_id", new_callable=AsyncMock, return_value=row),
            patch("app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None),
        ):
            try:
                resp = await client.get(f"/api/v1/events/{uuid.uuid4()}")
                assert resp.status_code == 200
                assert resp.json()["title"] == "Test Event"
            finally:
                _clear_overrides()

    @pytest.mark.asyncio
    async def test_delete_event_requires_admin(self, client):
        _override_auth(role="MEMBER")
        try:
            resp = await client.delete(f"/api/v1/events/{uuid.uuid4()}")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.asyncio
    async def test_update_event_empty_content(self, client):
        payload, uid = _override_auth(role="ADMIN")
        try:
            resp = await client.put(
                f"/api/v1/events/{uuid.uuid4()}",
                json={"content": "", "version": 1},
            )
            # Should be rejected (422) for empty content
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.asyncio
    async def test_create_event_comment_requires_member(self, client):
        _override_auth(role="GUEST")
        try:
            resp = await client.post(
                f"/api/v1/events/{uuid.uuid4()}/comments",
                json={"content": "Hello"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.asyncio
    async def test_get_event_comments(self, client):
        payload, uid = _override_auth(role="MEMBER")
        row = _make_event_row()

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())

        with (
            patch(f"{_SVC}.event_repo.find_by_id", new_callable=AsyncMock, return_value=row),
            patch("app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None),
            patch(f"{_COMMENT_SVC}.comment_repo.find_many", new_callable=AsyncMock, return_value=([], 0)),
            patch(f"{_COMMENT_SVC}.get_redis", return_value=mock_redis),
        ):
            try:
                resp = await client.get(f"/api/v1/events/{uuid.uuid4()}/comments")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 0
            finally:
                _clear_overrides()


# ── Comment Integration (event_id path) ──


class TestEventCommentService:
    @pytest.mark.asyncio
    async def test_create_comment_on_event(self, mock_pool, mock_conn):
        event_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        event_row = {
            "id": event_id,
            "user_id": uuid.uuid4(),
            "allow_comments": True,
            "comment_count": 0,
        }

        comment_row = {
            "id": uuid.uuid4(),
            "post_id": None,
            "event_id": event_id,
            "user_id": uuid.UUID(user_id),
            "parent_id": None,
            "content": "Nice event!",
            "mentions": None,
            "reactions": None,
            "vote_score": 0,
            "is_best_answer": False,
            "is_deleted": False,
            "created_at": _NOW,
            "updated_at": _NOW,
            "author_id": uuid.UUID(user_id),
            "author_username": "testuser",
            "author_display_name": "Test User",
            "author_avatar_url": None,
        }

        mock_conn.fetchrow = AsyncMock(side_effect=[event_row, comment_row])
        mock_conn.fetchval = AsyncMock(return_value=None)

        with (
            patch(f"{_COMMENT_SVC}.get_pool", return_value=mock_pool),
            patch(f"{_COMMENT_SVC}.emit", new_callable=AsyncMock),
            patch("app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None),
        ):
            from app.services.comment import create_comment

            result = await create_comment(
                post_id=None,
                user_id=user_id,
                content="Nice event!",
                event_id=event_id,
            )
        assert result["event_id"] == str(event_id)
        assert result["post_id"] is None

    @pytest.mark.asyncio
    async def test_create_comment_on_event_comments_disabled(self, mock_pool, mock_conn):
        event_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        event_row = {
            "id": event_id,
            "user_id": uuid.uuid4(),
            "allow_comments": False,
            "comment_count": 0,
        }

        mock_conn.fetchrow = AsyncMock(return_value=event_row)

        with patch(f"{_COMMENT_SVC}.get_pool", return_value=mock_pool):
            from app.services.comment import create_comment

            with pytest.raises(ValueError, match="Comments are disabled"):
                await create_comment(
                    post_id=None,
                    user_id=user_id,
                    content="Should fail",
                    event_id=event_id,
                )
