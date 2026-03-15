"""Tests for co-author service, repo, and endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SVC = "app.services.co_author"
_REPO = "app.repositories.co_author_repo"


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


def _make_co_author_row(post_id=None, user_id=None, status="ACCEPTED"):
    now = datetime.now(timezone.utc)
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
        "invited_at": now,
        "responded_at": now if status != "PENDING" else None,
        "user_display_name": "Test User",
        "user_avatar_url": None,
    }


# --- Repository tests ---


@pytest.mark.asyncio
async def test_insert_co_author(mock_conn):
    from app.repositories import co_author_repo

    row = _make_co_author_row()
    mock_conn.fetchrow = AsyncMock(return_value=row)
    result = await co_author_repo.insert_co_author(
        mock_conn, row["id"], row["post_id"], row["user_id"],
        "Test", None, None, False, "PENDING", row["invited_by"],
    )
    assert result["id"] == row["id"]
    mock_conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_find_co_authors_by_post(mock_conn):
    from app.repositories import co_author_repo

    post_id = uuid.uuid4()
    rows = [_make_co_author_row(post_id=post_id) for _ in range(3)]
    mock_conn.fetch = AsyncMock(return_value=rows)
    result = await co_author_repo.find_co_authors_by_post(mock_conn, post_id)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_find_co_authors_batch(mock_conn):
    from app.repositories import co_author_repo

    post_ids = [uuid.uuid4() for _ in range(2)]
    rows = [_make_co_author_row(post_id=pid) for pid in post_ids]
    mock_conn.fetch = AsyncMock(return_value=rows)
    result = await co_author_repo.find_co_authors_batch(mock_conn, post_ids)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_is_accepted_co_author_true(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.fetchval = AsyncMock(return_value=1)
    result = await co_author_repo.is_accepted_co_author(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_is_accepted_co_author_false(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.fetchval = AsyncMock(return_value=None)
    result = await co_author_repo.is_accepted_co_author(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_count_co_authors(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.fetchval = AsyncMock(return_value=5)
    result = await co_author_repo.count_co_authors(mock_conn, uuid.uuid4())
    assert result == 5


@pytest.mark.asyncio
async def test_delete_co_author(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 1")
    result = await co_author_repo.delete_co_author(mock_conn, uuid.uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_delete_co_author_not_found(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 0")
    result = await co_author_repo.delete_co_author(mock_conn, uuid.uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_update_status(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    now = datetime.now(timezone.utc)
    result = await co_author_repo.update_status(mock_conn, uuid.uuid4(), "ACCEPTED", now)
    assert result is True


@pytest.mark.asyncio
async def test_find_pending_invitations_empty(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.fetch = AsyncMock(return_value=[])
    result, total = await co_author_repo.find_pending_invitations(
        mock_conn, uuid.uuid4(), 1, 20
    )
    assert result == []
    assert total == 0


@pytest.mark.asyncio
async def test_find_existing_by_user(mock_conn):
    from app.repositories import co_author_repo

    row = _make_co_author_row()
    mock_conn.fetchrow = AsyncMock(return_value=row)
    result = await co_author_repo.find_existing_by_user(
        mock_conn, row["post_id"], row["user_id"]
    )
    assert result is not None


@pytest.mark.asyncio
async def test_delete_by_user_id(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 3")
    result = await co_author_repo.delete_by_user_id(mock_conn, uuid.uuid4())
    assert result == 3


# --- Service tests ---


@pytest.mark.asyncio
async def test_service_list_co_authors():
    from app.services.co_author import list_co_authors

    post_id = uuid.uuid4()
    rows = [_make_co_author_row(post_id=post_id)]
    with (
        patch(f"{_SVC}.get_pool") as mock_pool,
        patch(f"{_REPO}.find_co_authors_by_post", new_callable=AsyncMock, return_value=rows),
    ):
        conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.return_value.acquire.return_value = cm

        result = await list_co_authors(None, post_id)
        assert len(result) == 1
        assert result[0]["post_id"] == str(post_id)


@pytest.mark.asyncio
async def test_service_list_pending_invitations():
    from app.services.co_author import list_pending_invitations

    user_id = str(uuid.uuid4())
    row = _make_co_author_row(status="PENDING")
    row["post_title"] = "Test Post"
    row["invited_by_name"] = "Inviter"
    with (
        patch(f"{_SVC}.get_pool") as mock_pool,
        patch(
            f"{_REPO}.find_pending_invitations",
            new_callable=AsyncMock,
            return_value=([row], 1),
        ),
    ):
        conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.return_value.acquire.return_value = cm

        invitations, total = await list_pending_invitations(None, user_id)
        assert total == 1
        assert len(invitations) == 1
