"""Tests for co-author leave (self-removal) feature."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import ForbiddenError, NotFoundError

_SVC = "app.services.co_author"
_REPO = "app.repositories.co_author_repo"


def _make_co_author_row(post_id=None, user_id=None, status="ACCEPTED"):
    return {
        "id": uuid.uuid4(),
        "post_id": post_id or uuid.uuid4(),
        "user_id": user_id or uuid.uuid4(),
        "display_name": "Test User",
        "affiliation": None,
        "orcid": None,
        "is_external": False,
        "status": status,
        "invited_by": uuid.uuid4(),
    }


@pytest.mark.asyncio
async def test_leave_co_authorship_success(mock_pool, mock_conn):
    """Co-author can remove themselves from a post."""
    from app.services.co_author import leave_co_authorship

    post_id = uuid.uuid4()
    user_id = uuid.uuid4()
    co_author_row = _make_co_author_row(post_id=post_id, user_id=user_id)
    co_author_id = co_author_row["id"]

    mock_conn.execute = AsyncMock(return_value="DELETE 1")

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(
            f"{_REPO}.find_co_author_by_id",
            new_callable=AsyncMock,
            return_value=co_author_row,
        ),
        patch(
            f"{_REPO}.delete_co_author",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_delete,
    ):
        result = await leave_co_authorship(post_id, co_author_id, str(user_id))
        assert result is True
        mock_delete.assert_called_once_with(mock_conn, co_author_id)


@pytest.mark.asyncio
async def test_leave_co_authorship_wrong_user(mock_pool, mock_conn):
    """Returns 403 when user is not the co-author."""
    from app.services.co_author import leave_co_authorship

    post_id = uuid.uuid4()
    actual_user_id = uuid.uuid4()
    other_user_id = str(uuid.uuid4())
    co_author_row = _make_co_author_row(post_id=post_id, user_id=actual_user_id)
    co_author_id = co_author_row["id"]

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(
            f"{_REPO}.find_co_author_by_id",
            new_callable=AsyncMock,
            return_value=co_author_row,
        ),
    ):
        with pytest.raises(ForbiddenError):
            await leave_co_authorship(post_id, co_author_id, other_user_id)


@pytest.mark.asyncio
async def test_leave_co_authorship_not_found(mock_pool, mock_conn):
    """Returns 404 when co-author doesn't exist."""
    from app.services.co_author import leave_co_authorship

    post_id = uuid.uuid4()
    co_author_id = uuid.uuid4()

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(
            f"{_REPO}.find_co_author_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        with pytest.raises(NotFoundError):
            await leave_co_authorship(post_id, co_author_id, str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_leave_co_authorship_wrong_post(mock_pool, mock_conn):
    """Returns 404 when co-author belongs to a different post."""
    from app.services.co_author import leave_co_authorship

    post_id = uuid.uuid4()
    different_post_id = uuid.uuid4()
    user_id = uuid.uuid4()
    co_author_row = _make_co_author_row(post_id=different_post_id, user_id=user_id)
    co_author_id = co_author_row["id"]

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(
            f"{_REPO}.find_co_author_by_id",
            new_callable=AsyncMock,
            return_value=co_author_row,
        ),
    ):
        with pytest.raises(NotFoundError):
            await leave_co_authorship(post_id, co_author_id, str(user_id))
