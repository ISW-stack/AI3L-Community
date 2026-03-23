"""Tests for post-level reactions (toggle endpoint + shared helper)."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

# ── Shared helper unit tests ──


@pytest.mark.asyncio
async def test_toggle_reaction_add_new():
    """toggle_reaction_jsonb adds a reaction when user hasn't reacted."""
    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    fake_conn = AsyncMock()
    row_id = uuid.uuid4()
    fake_conn.fetchrow.return_value = {"reactions": None}

    result = await toggle_reaction_jsonb(fake_conn, "posts", row_id, "user1", "LIKE")

    assert result == {"LIKE": ["user1"]}
    # Two execute calls: update reactions + sync like_count for posts table
    assert fake_conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_toggle_reaction_remove_existing():
    """toggle_reaction_jsonb removes a reaction when user already reacted."""
    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    fake_conn = AsyncMock()
    row_id = uuid.uuid4()
    fake_conn.fetchrow.return_value = {"reactions": json.dumps({"LIKE": ["user1", "user2"]})}

    result = await toggle_reaction_jsonb(fake_conn, "posts", row_id, "user1", "LIKE")

    assert result == {"LIKE": ["user2"]}


@pytest.mark.asyncio
async def test_toggle_reaction_removes_empty_key():
    """toggle_reaction_jsonb removes reaction key when last user unreacts."""
    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    fake_conn = AsyncMock()
    row_id = uuid.uuid4()
    fake_conn.fetchrow.return_value = {"reactions": json.dumps({"LIKE": ["user1"]})}

    result = await toggle_reaction_jsonb(fake_conn, "posts", row_id, "user1", "LIKE")

    assert result == {}


@pytest.mark.asyncio
async def test_toggle_reaction_row_not_found():
    """toggle_reaction_jsonb raises ValueError when row is missing."""
    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = None

    with pytest.raises(ValueError, match="not found"):
        await toggle_reaction_jsonb(fake_conn, "posts", uuid.uuid4(), "user1", "LIKE")


@pytest.mark.asyncio
async def test_toggle_reaction_jsonb_string_parse():
    """toggle_reaction_jsonb handles reactions stored as JSON string."""
    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    fake_conn = AsyncMock()
    row_id = uuid.uuid4()
    fake_conn.fetchrow.return_value = {"reactions": '{"SMILE": ["u1"]}'}

    result = await toggle_reaction_jsonb(fake_conn, "posts", row_id, "u2", "SMILE")

    assert result == {"SMILE": ["u1", "u2"]}


@pytest.mark.asyncio
async def test_toggle_reaction_dict_parse():
    """toggle_reaction_jsonb handles reactions stored as dict (asyncpg JSONB auto-parse)."""
    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    fake_conn = AsyncMock()
    row_id = uuid.uuid4()
    fake_conn.fetchrow.return_value = {"reactions": {"CRY": ["u1"]}}

    result = await toggle_reaction_jsonb(fake_conn, "posts", row_id, "u2", "CRY")

    assert result == {"CRY": ["u1", "u2"]}


# ── Endpoint tests ──


MOCK_USER = {
    "sub": str(uuid.uuid4()),
    "role": "MEMBER",
    "username": "testuser",
    "jti": str(uuid.uuid4()),
}

MOCK_POST_ROW = {
    "id": uuid.uuid4(),
    "title": "Test Post",
    "content": "<p>Hello</p>",
    "author_id": uuid.uuid4(),
    "author_username": "testuser",
    "author_display_name": "Test User",
    "author_avatar_url": None,
    "category_id": None,
    "category_name": None,
    "keywords": None,
    "allow_comments": True,
    "version": 1,
    "comment_count": 0,
    "is_pinned": False,
    "view_count": 0,
    "reactions": json.dumps({"LIKE": [MOCK_USER["sub"]]}),
    "last_comment_at": None,
    "created_at": MagicMock(isoformat=lambda: "2026-01-01T00:00:00"),
    "updated_at": MagicMock(isoformat=lambda: "2026-01-01T00:00:00"),
}


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.posts.check_rate_limit", new_callable=AsyncMock, return_value=True)
@patch("app.api.v1.endpoints.posts.toggle_post_reaction")
async def test_toggle_post_reaction_success(mock_toggle, mock_rl, client):
    from app.converters.post_converter import row_to_post
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    try:
        mock_toggle.return_value = row_to_post(MOCK_POST_ROW)

        resp = await client.post(
            f"/api/v1/posts/{MOCK_POST_ROW['id']}/reactions",
            json={"reaction": "LIKE"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "reaction_counts" in data
        mock_toggle.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.posts.check_rate_limit", new_callable=AsyncMock, return_value=True)
@patch("app.api.v1.endpoints.posts.toggle_post_reaction")
async def test_toggle_post_reaction_not_found(mock_toggle, mock_rl, client):
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    try:
        mock_toggle.return_value = None

        resp = await client.post(
            f"/api/v1/posts/{uuid.uuid4()}/reactions",
            json={"reaction": "LIKE"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_toggle_post_reaction_invalid_type(client):
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    try:
        resp = await client.post(
            f"/api/v1/posts/{uuid.uuid4()}/reactions",
            json={"reaction": "INVALID"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.posts.check_rate_limit", new_callable=AsyncMock, return_value=True)
@patch("app.api.v1.endpoints.posts.toggle_post_reaction")
async def test_toggle_post_reaction_smile(mock_toggle, mock_rl, client):
    from app.converters.post_converter import row_to_post
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    try:
        post_row = dict(MOCK_POST_ROW)
        post_row["reactions"] = json.dumps({"SMILE": [MOCK_USER["sub"]]})
        mock_toggle.return_value = row_to_post(post_row)

        resp = await client.post(
            f"/api/v1/posts/{post_row['id']}/reactions",
            json={"reaction": "SMILE"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["reaction_counts"]["SMILE"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.posts.check_rate_limit", new_callable=AsyncMock, return_value=True)
@patch("app.api.v1.endpoints.posts.toggle_post_reaction")
async def test_toggle_post_reaction_cry(mock_toggle, mock_rl, client):
    from app.converters.post_converter import row_to_post
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    try:
        post_row = dict(MOCK_POST_ROW)
        post_row["reactions"] = json.dumps({"CRY": [MOCK_USER["sub"]]})
        mock_toggle.return_value = row_to_post(post_row)

        resp = await client.post(
            f"/api/v1/posts/{post_row['id']}/reactions",
            json={"reaction": "CRY"},
        )
        assert resp.status_code == status.HTTP_200_OK
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.posts.check_rate_limit", new_callable=AsyncMock, return_value=False)
async def test_toggle_post_reaction_rate_limited(mock_rl, client):
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    try:
        resp = await client.post(
            f"/api/v1/posts/{uuid.uuid4()}/reactions",
            json={"reaction": "LIKE"},
        )
        assert resp.status_code == 429
    finally:
        app.dependency_overrides.clear()


# ── Service tests ──


@pytest.mark.asyncio
@patch("app.services.post.post_repo")
async def test_toggle_post_reaction_service_found(mock_repo):
    from app.services.post import toggle_post_reaction

    post_id = uuid.uuid4()
    mock_repo.toggle_reaction = AsyncMock(return_value=MOCK_POST_ROW)

    result = await toggle_post_reaction(post_id, MOCK_USER["sub"], "LIKE")
    assert result is not None
    assert result["title"] == "Test Post"


@pytest.mark.asyncio
@patch("app.services.post.post_repo")
async def test_toggle_post_reaction_service_not_found(mock_repo):
    from app.services.post import toggle_post_reaction

    mock_repo.toggle_reaction = AsyncMock(return_value=None)

    result = await toggle_post_reaction(uuid.uuid4(), MOCK_USER["sub"], "LIKE")
    assert result is None


# ── Converter tests ──


def test_post_converter_includes_reaction_counts():
    from app.converters.post_converter import row_to_post

    row = dict(MOCK_POST_ROW)
    result = row_to_post(row)
    assert "reaction_counts" in result
    assert result["reaction_counts"] == {"LIKE": 1}
    assert result["user_reactions"] is None
    assert result["_raw_reactions"] == {"LIKE": [MOCK_USER["sub"]]}


def test_post_converter_null_reactions():
    from app.converters.post_converter import row_to_post

    row = dict(MOCK_POST_ROW)
    row["reactions"] = None
    result = row_to_post(row)
    assert result["reaction_counts"] is None


def test_post_converter_dict_reactions():
    from app.converters.post_converter import row_to_post

    row = dict(MOCK_POST_ROW)
    row["reactions"] = {"SMILE": ["u1", "u2"]}
    result = row_to_post(row)
    assert result["reaction_counts"] == {"SMILE": 2}
    assert result["_raw_reactions"] == {"SMILE": ["u1", "u2"]}
