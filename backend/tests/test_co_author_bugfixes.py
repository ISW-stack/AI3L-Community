"""Tests for co-author bugfixes (BUG 2, 3, 4, 8, 9)."""

import inspect
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SVC = "app.services.co_author"
_REPO = "app.repositories.co_author_repo"


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


# ---------------------------------------------------------------------------
# BUG 2: respond_to_invitation TOCTOU race — uses transaction + FOR UPDATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_to_invitation_uses_transaction_and_for_update(mock_pool, mock_conn):
    """BUG 2: respond_to_invitation wraps read+write in a transaction with FOR UPDATE."""
    from app.services.co_author import respond_to_invitation

    co_author_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    post_id = uuid.uuid4()

    invitation_row = {
        "id": co_author_id,
        "post_id": post_id,
        "user_id": uuid.UUID(user_id),
        "status": "PENDING",
        "display_name": "Invitee",
    }

    # Track fetchrow calls to verify FOR UPDATE query
    fetchrow_queries: list[str] = []

    async def tracking_fetchrow(query, *args):
        fetchrow_queries.append(query)
        if "FOR UPDATE" in query:
            return invitation_row
        # For the emit block's fetchrow calls
        if "posts" in query:
            return {"user_id": uuid.uuid4(), "title": "Test"}
        if "users" in query:
            return {"display_name": "Responder"}
        return None

    mock_conn.fetchrow = AsyncMock(side_effect=tracking_fetchrow)

    # Second pool for emit block
    conn2 = AsyncMock()
    conn2.fetchrow = AsyncMock(
        side_effect=[
            {"user_id": uuid.uuid4(), "title": "Test"},
            {"display_name": "Responder"},
        ]
    )
    cm2 = AsyncMock()
    cm2.__aenter__ = AsyncMock(return_value=conn2)
    cm2.__aexit__ = AsyncMock(return_value=False)
    pool2 = MagicMock()
    pool2.acquire.return_value = cm2

    pool_calls = [0]

    def get_pool_side_effect():
        pool_calls[0] += 1
        if pool_calls[0] <= 1:
            return mock_pool
        return pool2

    with (
        patch(f"{_SVC}.get_pool", side_effect=get_pool_side_effect),
        patch(f"{_REPO}.update_status", new_callable=AsyncMock, return_value=True),
        patch(f"{_SVC}.emit", new_callable=AsyncMock),
    ):
        result = await respond_to_invitation(co_author_id, user_id, True)
        assert result is True

        # Verify transaction was opened
        mock_conn.transaction.assert_called_once()

        # Verify FOR UPDATE was used in the SELECT
        assert any(
            "FOR UPDATE" in q for q in fetchrow_queries
        ), f"Expected FOR UPDATE in queries, got: {fetchrow_queries}"


@pytest.mark.asyncio
async def test_respond_to_invitation_rejects_non_pending(mock_pool, mock_conn):
    """BUG 2: Already-responded invitation returns 409."""
    from app.core.errors import AppError
    from app.services.co_author import respond_to_invitation

    co_author_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    invitation_row = {
        "id": co_author_id,
        "post_id": uuid.uuid4(),
        "user_id": uuid.UUID(user_id),
        "status": "ACCEPTED",  # Already responded
    }

    mock_conn.fetchrow = AsyncMock(return_value=invitation_row)

    with patch(f"{_SVC}.get_pool", return_value=mock_pool):
        with pytest.raises(AppError) as exc_info:
            await respond_to_invitation(co_author_id, user_id, True)
        assert exc_info.value.status_code == 409
        assert "already been responded" in exc_info.value.detail["message"]


@pytest.mark.asyncio
async def test_respond_to_invitation_rejects_wrong_user(mock_pool, mock_conn):
    """BUG 2: Wrong user gets 403 ForbiddenError."""
    from app.core.errors import AppError
    from app.services.co_author import respond_to_invitation

    co_author_id = uuid.uuid4()
    actual_user_id = str(uuid.uuid4())
    wrong_user_id = str(uuid.uuid4())

    invitation_row = {
        "id": co_author_id,
        "post_id": uuid.uuid4(),
        "user_id": uuid.UUID(actual_user_id),
        "status": "PENDING",
    }

    mock_conn.fetchrow = AsyncMock(return_value=invitation_row)

    with patch(f"{_SVC}.get_pool", return_value=mock_pool):
        with pytest.raises(AppError) as exc_info:
            await respond_to_invitation(co_author_id, wrong_user_id, True)
        assert exc_info.value.status_code == 403
        assert "not the target" in exc_info.value.detail["message"]


# ---------------------------------------------------------------------------
# BUG 3: Pending invitations for deleted posts still visible
# ---------------------------------------------------------------------------


def test_find_pending_invitations_excludes_deleted_posts():
    """BUG 3: find_pending_invitations SQL must contain 'is_deleted = false'."""
    source = inspect.getsource(
        __import__(
            "app.repositories.co_author_repo", fromlist=["find_pending_invitations"]
        ).find_pending_invitations
    )
    assert (
        "is_deleted = false" in source or "is_deleted=false" in source
    ), "find_pending_invitations must filter out deleted posts with is_deleted = false"


# ---------------------------------------------------------------------------
# BUG 4: Pending invitations from deleted inviters disappear
# ---------------------------------------------------------------------------


def test_find_pending_invitations_uses_left_join_for_inviter():
    """BUG 4: find_pending_invitations must use LEFT JOIN (not INNER JOIN) for inviter."""
    source = inspect.getsource(
        __import__(
            "app.repositories.co_author_repo", fromlist=["find_pending_invitations"]
        ).find_pending_invitations
    )
    assert (
        "LEFT JOIN users inviter" in source or "LEFT JOIN users inviter" in source
    ), "find_pending_invitations must use LEFT JOIN for inviter to handle deleted inviters"
    # Ensure it's not an INNER JOIN
    # The SQL should not have a bare "JOIN users inviter" without LEFT
    lines = source.split("\n")
    for line in lines:
        stripped = line.strip()
        if "JOIN users inviter" in stripped and "LEFT" not in stripped:
            pytest.fail(f"Found INNER JOIN for inviter (missing LEFT): {stripped}")


# ---------------------------------------------------------------------------
# BUG 8: Duplicate external co-author causes unhandled 500
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_external_co_author_duplicate_returns_409(mock_pool, mock_conn):
    """BUG 8: UniqueViolationError on insert should return COAUTHOR_002 / 409."""
    from app.core.errors import AppError
    from app.services.co_author import add_external_co_author

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    post_row = {"id": post_id, "user_id": uuid.UUID(user_id)}
    mock_conn.fetchrow = AsyncMock(return_value=post_row)

    # Create a fake UniqueViolationError
    class UniqueViolationError(Exception):
        pass

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_REPO}.count_co_authors", new_callable=AsyncMock, return_value=0),
        patch(
            f"{_REPO}.insert_co_author",
            new_callable=AsyncMock,
            side_effect=UniqueViolationError("duplicate key"),
        ),
    ):
        with pytest.raises(AppError) as exc_info:
            await add_external_co_author(post_id, user_id, "External Author", "MIT")
        assert exc_info.value.status_code == 409
        assert "COAUTHOR_002" in exc_info.value.detail["code"]
        assert "already exists" in exc_info.value.detail["message"]


# ---------------------------------------------------------------------------
# BUG 9: Converter returns no avatar for freshly-created co-author
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invite_co_author_response_includes_avatar():
    """BUG 9: invite_co_author enriches the row with user_display_name and user_avatar_url."""
    from app.services.co_author import invite_co_author

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    target_user_id = str(uuid.uuid4())
    avatar_url = "avatars/test-avatar.png"

    post_row = {"id": post_id, "user_id": uuid.UUID(user_id), "title": "Test Post"}
    target_row = {
        "id": uuid.UUID(target_user_id),
        "display_name": "Target User",
        "avatar_url": avatar_url,
    }
    co_author_row = _make_co_author_row(
        post_id=post_id, user_id=uuid.UUID(target_user_id), status="PENDING"
    )
    # Remove pre-set user fields to simulate raw INSERT RETURNING (no JOIN)
    co_author_row.pop("user_display_name", None)
    co_author_row.pop("user_avatar_url", None)

    conn = AsyncMock()
    # fetchrow: first call = post_row, second call = target_row
    conn.fetchrow = AsyncMock(side_effect=[post_row, target_row])
    conn.execute = AsyncMock(return_value="SELECT 1")

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm

    # Second pool for emit block
    inviter_row = {"display_name": "Inviter"}
    conn2 = AsyncMock()
    conn2.fetchrow = AsyncMock(return_value=inviter_row)
    cm2 = AsyncMock()
    cm2.__aenter__ = AsyncMock(return_value=conn2)
    cm2.__aexit__ = AsyncMock(return_value=False)

    pool_calls = [0]

    def get_pool_side_effect():
        pool_calls[0] += 1
        if pool_calls[0] <= 1:
            return pool
        pool2 = MagicMock()
        pool2.acquire.return_value = cm2
        return pool2

    # Capture what gets passed to the converter
    _captured_row = {}  # noqa: F841

    async def mock_insert(conn, *args):
        return dict(co_author_row)

    with (
        patch(f"{_SVC}.get_pool", side_effect=get_pool_side_effect),
        patch(f"{_SVC}.get_redis") as _mock_redis,  # noqa: F841
        patch(
            f"{_SVC}.get_blocked_user_ids",
            new_callable=AsyncMock,
            return_value=set(),
        ),
        patch(f"{_REPO}.count_co_authors", new_callable=AsyncMock, return_value=0),
        patch(
            f"{_REPO}.find_existing_by_user",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(f"{_REPO}.insert_co_author", side_effect=mock_insert),
        patch(f"{_SVC}.emit", new_callable=AsyncMock),
    ):
        result = await invite_co_author(post_id, user_id, target_user_id)

        # The converter should have received user_avatar_url from enrichment
        # and resolved it. The result should contain the avatar.
        assert result is not None
        # avatar_url should be present (not None) since we provided one
        assert result.get("avatar_url") is not None or avatar_url in str(
            result
        ), f"Expected avatar in response, got: {result}"
        # display_name should come from target user
        assert result["display_name"] == "Target User"
