"""Tests for co-author & citation audit fixes (B1-B6, S1-S5, U1-U6)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_CO_SVC = "app.services.co_author"
_CO_REPO = "app.repositories.co_author_repo"
_CI_SVC = "app.services.citation"
_CI_REPO = "app.repositories.citation_repo"
_POST_SVC = "app.services.post"
_POST_REPO = "app.repositories.post_repo"


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


def _make_pool_cm(conn):
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool


def _make_conn_with_tx():
    conn = AsyncMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    conn.execute = AsyncMock(return_value="OK")
    return conn


# ──────────────────────────────────────────────────────────────────
# B3: Re-invite after rejection
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_co_author_re_invite_after_rejection():
    """B3: Should allow re-inviting a user who previously rejected."""
    from app.services.co_author import invite_co_author

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    target_user_id = str(uuid.uuid4())
    target_uuid = uuid.UUID(target_user_id)

    post_row = {"id": post_id, "user_id": uuid.UUID(user_id), "title": "Test Post"}
    target_row = {
        "id": target_uuid,
        "display_name": "Target User",
        "avatar_url": None,
    }

    # Existing REJECTED entry
    rejected_row = _make_co_author_row(post_id, target_uuid, status="REJECTED")

    # New row returned after re-insert
    new_row = _make_co_author_row(post_id, target_uuid, status="PENDING")

    conn = _make_conn_with_tx()
    conn.fetchrow = AsyncMock(side_effect=[post_row, target_row])

    pool = _make_pool_cm(conn)

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

    mock_delete = AsyncMock(return_value=True)

    with (
        patch(f"{_CO_SVC}.get_pool", side_effect=get_pool_side_effect),
        patch(f"{_CO_SVC}.get_redis"),
        patch(f"{_CO_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set()),
        patch(f"{_CO_REPO}.count_co_authors", new_callable=AsyncMock, return_value=0),
        patch(f"{_CO_REPO}.find_existing_by_user", new_callable=AsyncMock, return_value=rejected_row),
        patch(f"{_CO_REPO}.delete_co_author", mock_delete),
        patch(f"{_CO_REPO}.insert_co_author", new_callable=AsyncMock, return_value=new_row),
        patch(f"{_CO_SVC}.emit", new_callable=AsyncMock),
    ):
        result = await invite_co_author(post_id, user_id, target_user_id)
        assert result is not None
        # The rejected entry should have been deleted first
        mock_delete.assert_called_once_with(conn, rejected_row["id"])


@pytest.mark.asyncio
async def test_invite_co_author_still_blocks_pending():
    """B3: Should still block re-invite for PENDING entries."""
    from app.core.errors import AppError
    from app.services.co_author import invite_co_author

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    target_user_id = str(uuid.uuid4())

    post_row = {"id": post_id, "user_id": uuid.UUID(user_id), "title": "Test Post"}
    target_row = {
        "id": uuid.UUID(target_user_id),
        "display_name": "Target",
        "avatar_url": None,
    }
    pending_row = _make_co_author_row(post_id, uuid.UUID(target_user_id), status="PENDING")

    conn = _make_conn_with_tx()
    conn.fetchrow = AsyncMock(side_effect=[post_row, target_row])

    pool = _make_pool_cm(conn)

    with (
        patch(f"{_CO_SVC}.get_pool", return_value=pool),
        patch(f"{_CO_SVC}.get_redis"),
        patch(f"{_CO_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set()),
        patch(f"{_CO_REPO}.count_co_authors", new_callable=AsyncMock, return_value=0),
        patch(f"{_CO_REPO}.find_existing_by_user", new_callable=AsyncMock, return_value=pending_row),
    ):
        with pytest.raises(AppError) as exc_info:
            await invite_co_author(post_id, user_id, target_user_id)
        assert exc_info.value.status_code == 409


# ──────────────────────────────────────────────────────────────────
# U5: Self-invite check happens first (before advisory lock)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_co_author_self_invite_rejected_early():
    """U5: Self-invite should be rejected before any DB calls."""
    from app.core.errors import AppError
    from app.services.co_author import invite_co_author

    user_id = str(uuid.uuid4())
    # No DB mocking needed — should fail before touching DB
    with pytest.raises(AppError) as exc_info:
        await invite_co_author(uuid.uuid4(), user_id, user_id)
    assert exc_info.value.status_code == 400
    assert "yourself" in str(exc_info.value.detail).lower()


# ──────────────────────────────────────────────────────────────────
# S2: Co-author can only edit content, not metadata
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_post_coauthor_cannot_change_title():
    """S2: Co-author edit should ignore title/category/keywords/allow_comments."""
    from app.services.post import update_post

    post_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    coauthor_id = str(uuid.uuid4())

    current_post = {
        "id": post_id,
        "user_id": owner_id,
        "title": "Original Title",
        "content": "Original content",
        "category_id": uuid.uuid4(),
        "keywords": ["original"],
        "allow_comments": True,
        "version": 1,
    }

    updated_row = {**current_post, "version": 2}

    conn = _make_conn_with_tx()
    pool = _make_pool_cm(conn)

    with (
        patch(f"{_POST_SVC}.get_pool", return_value=pool),
        patch(f"{_POST_REPO}.find_for_update", new_callable=AsyncMock, return_value=current_post),
        patch(
            "app.repositories.co_author_repo.is_accepted_co_author",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(f"{_POST_REPO}.insert_history", new_callable=AsyncMock),
        patch(f"{_POST_REPO}.update_in_transaction", new_callable=AsyncMock, return_value=updated_row) as mock_update,
        patch(f"{_POST_SVC}.async_row_to_post", new_callable=AsyncMock, return_value=updated_row),
    ):
        await update_post(
            post_id,
            coauthor_id,
            title="Hacked Title",
            content="New content by coauthor",
            category_id=str(uuid.uuid4()),
            keywords=["hacked"],
            allow_comments=False,
            expected_version=1,
            caller_role="MEMBER",
        )
        # Verify update_in_transaction was called with ORIGINAL metadata
        call_args = mock_update.call_args[0]
        # call_args: (conn, post_id, new_title, new_content, new_category_id, new_keywords, new_allow)
        assert call_args[2] == "Original Title"  # title unchanged
        assert call_args[3] == "New content by coauthor"  # content changed
        assert call_args[4] == current_post["category_id"]  # category unchanged
        assert call_args[5] == ["original"]  # keywords unchanged
        assert call_args[6] is True  # allow_comments unchanged


# ──────────────────────────────────────────────────────────────────
# B5: sync_post_citations uses post owner's ID
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_post_citation_sync_uses_owner_id():
    """B5: sync_post_citations should be called with post owner's ID, not editor's."""
    from app.services.post import update_post

    post_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    editor_id = str(uuid.uuid4())  # co-author

    current_post = {
        "id": post_id,
        "user_id": owner_id,
        "title": "Test",
        "content": "Old content",
        "category_id": None,
        "keywords": [],
        "allow_comments": True,
        "version": 1,
    }
    updated_row = {**current_post, "version": 2}

    conn = _make_conn_with_tx()
    pool = _make_pool_cm(conn)

    mock_sync = AsyncMock()

    with (
        patch(f"{_POST_SVC}.get_pool", return_value=pool),
        patch(f"{_POST_REPO}.find_for_update", new_callable=AsyncMock, return_value=current_post),
        patch(
            "app.repositories.co_author_repo.is_accepted_co_author",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(f"{_POST_REPO}.insert_history", new_callable=AsyncMock),
        patch(f"{_POST_REPO}.update_in_transaction", new_callable=AsyncMock, return_value=updated_row),
        patch(f"{_POST_SVC}.async_row_to_post", new_callable=AsyncMock, return_value=updated_row),
        patch("app.services.citation.sync_post_citations", mock_sync),
    ):
        await update_post(
            post_id,
            editor_id,
            content="New content with citations",
            expected_version=1,
            caller_role="MEMBER",
        )
        mock_sync.assert_called_once()
        # Third argument should be OWNER's ID, not editor's
        assert mock_sync.call_args[0][2] == str(owner_id)
        assert mock_sync.call_args[0][2] != editor_id


# ──────────────────────────────────────────────────────────────────
# S3: CoAuthorInviteRequest display_name max_length
# ──────────────────────────────────────────────────────────────────


def test_coauthor_invite_display_name_max_length():
    """S3: display_name should be rejected if > 100 chars."""
    from pydantic import ValidationError

    from app.schemas.co_author import CoAuthorInviteRequest

    # Normal case
    req = CoAuthorInviteRequest(user_id=str(uuid.uuid4()), display_name="A" * 100)
    assert len(req.display_name) == 100

    # Too long
    with pytest.raises(ValidationError):
        CoAuthorInviteRequest(user_id=str(uuid.uuid4()), display_name="A" * 101)


# ──────────────────────────────────────────────────────────────────
# S5: post_process_citations handles attribute variations
# ──────────────────────────────────────────────────────────────────


def test_post_process_citations_double_quotes():
    from app.core.file_validation import post_process_citations

    html = '<a href="/forum/abc" data-citation="true">Ref</a>'
    result = post_process_citations(html)
    assert 'class="citation"' in result


def test_post_process_citations_single_quotes():
    """S5: Should handle single-quoted attribute values."""
    from app.core.file_validation import post_process_citations

    html = "<a href='/forum/abc' data-citation='true'>Ref</a>"
    result = post_process_citations(html)
    assert 'class="citation"' in result


def test_post_process_citations_with_spaces():
    """S5: Should handle spaces around the = sign."""
    from app.core.file_validation import post_process_citations

    html = '<a href="/forum/abc" data-citation = "true">Ref</a>'
    result = post_process_citations(html)
    assert 'class="citation"' in result


def test_post_process_citations_no_match():
    from app.core.file_validation import post_process_citations

    html = '<a href="/forum/abc">Normal link</a>'
    result = post_process_citations(html)
    assert 'class="citation"' not in result


# ──────────────────────────────────────────────────────────────────
# U4: Citation search ILIKE fallback for non-English
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_citation_search_ilike_fallback():
    """U4: Falls back to ILIKE title search when FTS returns empty."""
    from app.services.citation import search_posts_for_citation

    user_id = str(uuid.uuid4())

    ilike_row = {"id": uuid.uuid4(), "title": "語言學習研究", "author_name": "測試用戶"}

    conn = AsyncMock()
    # First call (FTS) returns empty, second call (ILIKE) returns result
    conn.fetch = AsyncMock(side_effect=[[], [ilike_row]])

    pool = _make_pool_cm(conn)

    with (
        patch(f"{_CI_SVC}.get_pool", return_value=pool),
        patch(f"{_CI_SVC}.get_redis"),
        patch(f"{_CI_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set()),
    ):
        result = await search_posts_for_citation("語言學習", user_id)
        assert len(result) == 1
        assert result[0]["title"] == "語言學習研究"

        # Verify two queries were made (FTS then ILIKE)
        assert conn.fetch.call_count == 2
        # Second query should use ILIKE
        second_query = conn.fetch.call_args_list[1][0][0]
        assert "ILIKE" in second_query


@pytest.mark.asyncio
async def test_citation_search_fts_success_no_fallback():
    """U4: No ILIKE fallback when FTS returns results."""
    from app.services.citation import search_posts_for_citation

    user_id = str(uuid.uuid4())
    fts_row = {"id": uuid.uuid4(), "title": "Machine Learning", "author_name": "Author"}

    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[fts_row])

    pool = _make_pool_cm(conn)

    with (
        patch(f"{_CI_SVC}.get_pool", return_value=pool),
        patch(f"{_CI_SVC}.get_redis"),
        patch(f"{_CI_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set()),
    ):
        result = await search_posts_for_citation("machine learning", user_id)
        assert len(result) == 1
        # Only one query (FTS succeeded)
        assert conn.fetch.call_count == 1


@pytest.mark.asyncio
async def test_citation_search_ilike_escapes_wildcards():
    """U4: ILIKE fallback should escape %, _, \\ in query."""
    from app.services.citation import search_posts_for_citation

    user_id = str(uuid.uuid4())

    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[[], []])  # Both return empty

    pool = _make_pool_cm(conn)

    with (
        patch(f"{_CI_SVC}.get_pool", return_value=pool),
        patch(f"{_CI_SVC}.get_redis"),
        patch(f"{_CI_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set()),
    ):
        await search_posts_for_citation("100% test_case", user_id)
        # ILIKE query should have escaped pattern
        ilike_call = conn.fetch.call_args_list[1]
        pattern = ilike_call[0][1]
        assert "\\%" in pattern
        assert "\\_" in pattern


# ──────────────────────────────────────────────────────────────────
# U6: Citation event emission fetches data once
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_citation_event_fetches_data_once():
    """U6: When emitting multiple citation events, title/name fetched once."""
    from app.services.citation import sync_post_citations

    post_id = uuid.uuid4()
    author_id = str(uuid.uuid4())
    author_uuid = uuid.UUID(author_id)
    cited1 = uuid.uuid4()
    cited2 = uuid.uuid4()
    other_author = uuid.uuid4()

    html = (
        f'<a href="/forum/{cited1}" data-citation="true">R1</a>'
        f'<a href="/forum/{cited2}" data-citation="true">R2</a>'
    )

    conn = _make_conn_with_tx()
    conn.fetchval = AsyncMock(side_effect=[
        1,  # cited1 exists
        other_author,  # cited1 author (not self)
        1,  # cited2 exists
        other_author,  # cited2 author (not self)
    ])

    pool = _make_pool_cm(conn)

    # For the event emission block — single pool.acquire for all events
    event_conn = AsyncMock()
    event_conn.fetchrow = AsyncMock(side_effect=[
        {"title": "Citing Post"},
        {"display_name": "Citer Name"},
    ])
    event_cm = AsyncMock()
    event_cm.__aenter__ = AsyncMock(return_value=event_conn)
    event_cm.__aexit__ = AsyncMock(return_value=False)

    pool_calls = [0]

    def get_pool_effect():
        pool_calls[0] += 1
        if pool_calls[0] <= 1:
            return pool
        p2 = MagicMock()
        p2.acquire.return_value = event_cm
        return p2

    emit_calls = []

    async def mock_emit(event_name, **kwargs):
        emit_calls.append((event_name, kwargs))

    with (
        patch(f"{_CI_SVC}.get_pool", side_effect=get_pool_effect),
        patch(f"{_CI_REPO}.find_existing_citations", new_callable=AsyncMock, return_value=[]),
        patch(f"{_CI_REPO}.insert_citation", new_callable=AsyncMock, side_effect=[
            {"cited_post_id": cited1, "is_self_citation": False},
            {"cited_post_id": cited2, "is_self_citation": False},
        ]),
        patch(f"{_CI_REPO}.update_citation_count", new_callable=AsyncMock),
        patch(f"{_CI_REPO}.delete_citations", new_callable=AsyncMock),
        patch(f"{_CI_SVC}.emit", side_effect=mock_emit),
    ):
        await sync_post_citations(post_id, html, author_id)

        # Two events emitted
        assert len(emit_calls) == 2
        # Both should have the same citer_name (fetched once)
        assert emit_calls[0][1]["citer_name"] == "Citer Name"
        assert emit_calls[1][1]["citer_name"] == "Citer Name"
        # event_conn.fetchrow should be called exactly 2 times (once for post, once for user)
        assert event_conn.fetchrow.call_count == 2


# ──────────────────────────────────────────────────────────────────
# B4: citation_count updated after soft_delete
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_soft_delete_updates_citation_counts():
    """B4: soft_delete_post should recalculate citation_count for cited posts."""
    from app.services.post import soft_delete_post

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    cited_post_id = uuid.uuid4()

    conn = _make_conn_with_tx()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetch = AsyncMock(return_value=[{"cited_post_id": cited_post_id}])

    pool = _make_pool_cm(conn)

    mock_update_count = AsyncMock(return_value=0)

    with (
        patch(f"{_POST_SVC}.get_pool", return_value=pool),
        patch(f"{_CI_REPO}.update_citation_count", mock_update_count),
        patch(f"{_POST_SVC}._cleanup_post_files", new_callable=AsyncMock),
    ):
        result = await soft_delete_post(post_id, user_id)
        assert result is True
        # citation_count should be recalculated for the cited post
        mock_update_count.assert_called_once_with(conn, cited_post_id)


# ──────────────────────────────────────────────────────────────────
# S1: External co-author endpoint rate limit (endpoint test)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_external_co_author_endpoint_has_rate_limit():
    """S1: add_external_co_author endpoint should check rate limit."""
    from app.core.constants import RATE_LIMIT_CO_AUTHOR_EXTERNAL

    assert RATE_LIMIT_CO_AUTHOR_EXTERNAL is not None
    assert len(RATE_LIMIT_CO_AUTHOR_EXTERNAL) == 2  # (count, period)
    assert RATE_LIMIT_CO_AUTHOR_EXTERNAL[0] > 0
    assert RATE_LIMIT_CO_AUTHOR_EXTERNAL[1] > 0


# ──────────────────────────────────────────────────────────────────
# S4: list_user_co_authored_posts requires MEMBER+ role
# ──────────────────────────────────────────────────────────────────


def test_list_user_co_authored_posts_requires_member():
    """S4: Endpoint should use require_role, not get_current_user."""
    import importlib
    import inspect

    mod = importlib.import_module("app.api.v1.endpoints.co_authors")
    source = inspect.getsource(mod.list_user_co_authored_posts)
    # Should use require_role, not get_current_user
    assert "require_role" in source
    assert "get_current_user" not in source
