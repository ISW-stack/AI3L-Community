"""Tests for M2 (co-authored posts endpoint), M4 (standalone form no-auth),
and M5/M6 (album comment/member direct ID lookup)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.anyio
async def test_list_co_authored_posts(mock_pool, mock_conn):
    """M2: list_co_authored_posts returns correct paginated data."""
    from app.services.co_author import list_co_authored_posts

    user_id = str(uuid.uuid4())
    post_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    fake_rows = [
        {
            "id": post_id,
            "title": "My Co-authored Post",
            "created_at": now,
        }
    ]

    mock_conn.fetch.return_value = [
        {**fake_rows[0], "_total": 1},
    ]

    with patch("app.services.co_author.get_pool", return_value=mock_pool):
        posts, total = await list_co_authored_posts(user_id, page=1, page_size=20)

    assert total == 1
    assert len(posts) == 1
    assert posts[0]["id"] == post_id
    assert posts[0]["title"] == "My Co-authored Post"
    # Verify _total is stripped from results
    assert "_total" not in posts[0]


@pytest.mark.anyio
async def test_standalone_form_accessible_without_auth(mock_pool, mock_conn):
    """M4: get_form endpoint allows anonymous access for standalone forms."""
    from app.api.v1.endpoints.forms import get_form

    form_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    fake_form = {
        "id": str(form_id),
        "title": "Public Survey",
        "description": None,
        "banner_url": None,
        "sig_id": None,
        "created_by": str(uuid.uuid4()),
        "created_by_name": "Test User",
        "deadline": None,
        "max_respondents": None,
        "questions": [],
        "allow_non_members": True,
        "is_deleted": False,
        "is_schema_locked": False,
        "is_active": True,
        "response_count": 0,
        "has_responded": False,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "user_is_sig_admin": False,
    }

    with patch(
        "app.api.v1.endpoints.forms.get_form_by_id",
        new_callable=AsyncMock,
        return_value=fake_form,
    ):
        # current_user=None simulates anonymous access
        result = await get_form(form_id=form_id, current_user=None)

    assert result.title == "Public Survey"
    assert result.user_is_sig_admin is False


@pytest.mark.anyio
async def test_create_comment_uses_direct_id_lookup(mock_pool, mock_conn):
    """M5: create_comment re-fetches via find_comment_by_id_with_user, not page scan."""
    from app.services.album import create_comment

    album_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    comment_id_val = uuid.uuid4()

    # find_album_by_id returns a valid album
    fake_album = {
        "id": uuid.UUID(album_id),
        "title": "Test Album",
        "created_by": uuid.UUID(user_id),
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }

    # insert_comment returns raw row
    fake_insert_row = {
        "id": comment_id_val,
        "album_id": uuid.UUID(album_id),
        "photo_id": None,
        "user_id": uuid.UUID(user_id),
        "parent_id": None,
        "content": "Hello",
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }

    # find_comment_by_id_with_user returns row with user JOINs
    fake_joined_row = {
        **fake_insert_row,
        "display_name": "TestUser",
        "avatar_url": None,
    }

    with (
        patch("app.services.album.get_pool", return_value=mock_pool),
        patch(
            "app.services.album.album_repo.find_album_by_id",
            new_callable=AsyncMock,
            return_value=fake_album,
        ),
        patch(
            "app.services.album.album_repo.insert_comment",
            new_callable=AsyncMock,
            return_value=fake_insert_row,
        ),
        patch(
            "app.services.album.album_repo.find_comment_by_id_with_user",
            new_callable=AsyncMock,
            return_value=fake_joined_row,
        ) as mock_find_by_id,
        patch(
            "app.services.album.album_repo.find_comments",
            new_callable=AsyncMock,
        ) as mock_find_comments,
    ):
        result = await create_comment(album_id, user_id, "Hello")

    # Verify direct ID lookup was called
    mock_find_by_id.assert_called_once()
    # Verify page-scan find_comments was NOT called
    mock_find_comments.assert_not_called()
    assert result["id"] == str(comment_id_val)
    assert result["display_name"] == "TestUser"
