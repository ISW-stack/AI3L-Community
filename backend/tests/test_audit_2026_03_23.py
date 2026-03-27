"""Tests for audit fixes dated 2026-03-23.

Covers: H-01, M-01, M-02, M-04, M-06, M-07, M-09, M-11,
        L-06, L-07, L-10, L-13, L-19.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helper: build a fake pool whose acquire() works as an async context manager
# ---------------------------------------------------------------------------


def _make_fake_pool(fake_conn: AsyncMock) -> MagicMock:
    """Return a mock pool where ``async with pool.acquire() as conn`` yields *fake_conn*."""

    @asynccontextmanager
    async def _acquire():
        yield fake_conn

    pool = MagicMock()
    pool.acquire = _acquire
    return pool


def _make_transactional_conn() -> AsyncMock:
    """Return an AsyncMock conn whose ``.transaction()`` works as async context manager."""
    conn = AsyncMock()

    @asynccontextmanager
    async def _transaction():
        yield

    conn.transaction = _transaction
    return conn


# ---------------------------------------------------------------------------
# H-01: post_repo.search fallback count query includes LEFT JOIN sigs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_h01_search_fallback_count_includes_sigs_join():
    """H-01: Fallback count query must include LEFT JOIN sigs to avoid 'column s does not exist'."""
    from app.repositories import post_repo

    fake_conn = AsyncMock()
    fake_conn.fetch.return_value = []  # empty results -> triggers fallback
    fake_conn.fetchval.return_value = 0

    fake_pool = _make_fake_pool(fake_conn)

    with patch("app.repositories.post_repo.get_pool", return_value=fake_pool):
        result, total, total_pages = await post_repo.search(keyword="test")

    assert result == []
    assert total == 0

    # Verify the fallback count query includes the sigs join
    fetchval_call = fake_conn.fetchval.call_args
    sql = fetchval_call[0][0]
    assert "LEFT JOIN sigs" in sql


# ---------------------------------------------------------------------------
# M-01: preferred_language accepts all 17 locales
# ---------------------------------------------------------------------------


def test_m01_preferred_language_all_locales():
    """M-01: All 17 frontend locales should be accepted."""
    from app.schemas.user import UserUpdateRequest

    all_locales = [
        "en", "zh-TW", "zh-CN", "ja", "fr", "es", "de", "ar", "hi",
        "id", "it", "ko", "nan", "pt", "ru", "tr", "vi",
    ]
    for locale in all_locales:
        req = UserUpdateRequest(preferred_language=locale)
        assert req.preferred_language == locale


def test_m01_preferred_language_rejects_invalid():
    """M-01: Invalid locale codes must be rejected."""
    from app.schemas.user import UserUpdateRequest

    with pytest.raises(ValidationError):
        UserUpdateRequest(preferred_language="xx")


def test_m01_preferred_language_rejects_empty():
    """M-01: Empty string must be rejected."""
    from app.schemas.user import UserUpdateRequest

    with pytest.raises(ValidationError):
        UserUpdateRequest(preferred_language="")


# ---------------------------------------------------------------------------
# M-02: post_process_citations idempotency
# ---------------------------------------------------------------------------


def test_m02_post_process_citations_adds_class():
    """M-02: post_process_citations should add class='citation' to citation links."""
    from app.core.file_validation import post_process_citations

    html = '<a data-citation="true" href="/posts/123">ref</a>'
    result = post_process_citations(html)
    assert 'class="citation"' in result


def test_m02_post_process_citations_idempotent():
    """M-02: Calling post_process_citations twice should not duplicate class attribute."""
    from app.core.file_validation import post_process_citations

    html = '<a data-citation="true" href="/posts/123">ref</a>'
    first = post_process_citations(html)
    assert 'class="citation"' in first

    second = post_process_citations(first)
    assert second.count('class="citation"') == 1  # Not duplicated


def test_m02_post_process_citations_no_citation():
    """M-02: Non-citation links should be unaffected."""
    from app.core.file_validation import post_process_citations

    html = '<a href="/posts/123">ref</a>'
    result = post_process_citations(html)
    assert 'class="citation"' not in result


# ---------------------------------------------------------------------------
# M-04: rate_limit get_client_ip prefers X-Real-IP
# ---------------------------------------------------------------------------


def test_m04_get_client_ip_prefers_real_ip():
    """M-04: get_client_ip should prefer X-Real-IP over X-Forwarded-For."""
    from app.core.rate_limit import get_client_ip

    request = MagicMock()
    request.headers = {
        "x-real-ip": "1.2.3.4",
        "x-forwarded-for": "10.0.0.1, 172.16.0.1",
    }
    request.client.host = "127.0.0.1"

    assert get_client_ip(request) == "1.2.3.4"


def test_m04_get_client_ip_falls_back_to_forwarded_for():
    """M-04: Without X-Real-IP, should use X-Forwarded-For."""
    from app.core.rate_limit import get_client_ip

    request = MagicMock()
    request.headers = {
        "x-forwarded-for": "10.0.0.1, 172.16.0.1",
    }
    request.client.host = "127.0.0.1"

    result = get_client_ip(request)
    # Should extract an IP from x-forwarded-for
    assert result is not None
    assert result != "127.0.0.1"


def test_m04_get_client_ip_falls_back_to_client_host():
    """M-04: Without proxy headers, should fall back to request.client.host."""
    from app.core.rate_limit import get_client_ip

    request = MagicMock()
    request.headers = {}
    request.client.host = "192.168.1.1"

    assert get_client_ip(request) == "192.168.1.1"


# ---------------------------------------------------------------------------
# M-06: ip_ban unban_ip uses DELETE ... RETURNING (single query, no TOCTOU)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m06_unban_ip_single_query():
    """M-06: unban_ip should use DELETE ... RETURNING instead of separate read+delete."""
    from app.services import ip_ban

    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = {"ip_address": "10.0.0.1"}

    fake_pool = _make_fake_pool(fake_conn)
    fake_redis = AsyncMock()

    with (
        patch("app.core.database.get_pool", return_value=fake_pool),
        patch("app.services.ip_ban.get_redis", return_value=fake_redis),
    ):
        result = await ip_ban.unban_ip(uuid.uuid4())

    assert result is True
    # Should use DELETE ... RETURNING (single call to fetchrow)
    sql = fake_conn.fetchrow.call_args[0][0]
    assert "DELETE" in sql
    assert "RETURNING" in sql
    # Cache set to "0" (not banned) so stale "1" never lingers
    fake_redis.set.assert_called_once_with("ip_ban:10.0.0.1", "0", ex=300)


@pytest.mark.asyncio
async def test_m06_unban_ip_not_found_returns_false():
    """M-06: unban_ip returns False when ban ID does not exist."""
    from app.services import ip_ban

    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = None  # Not found

    fake_pool = _make_fake_pool(fake_conn)
    fake_redis = AsyncMock()

    with (
        patch("app.core.database.get_pool", return_value=fake_pool),
        patch("app.services.ip_ban.get_redis", return_value=fake_redis),
    ):
        result = await ip_ban.unban_ip(uuid.uuid4())

    assert result is False
    fake_redis.delete.assert_not_called()


# ---------------------------------------------------------------------------
# M-07: get_post_by_id returns post-increment view count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m07_get_post_by_id_returns_incremented_view_count():
    """M-07: When increment_view=True, returned view_count should be +1."""
    from app.services import post as post_service

    post_id = uuid.uuid4()
    user_id = uuid.uuid4()
    viewer_id = str(uuid.uuid4())

    fake_row = {
        "id": post_id,
        "title": "Test",
        "content": "Hello",
        "user_id": user_id,
        "author_id": user_id,
        "author_username": "test",
        "author_display_name": "Test User",
        "author_avatar_url": None,
        "category_id": None,
        "category_name": None,
        "sig_id": None,
        "sig_name": None,
        "keywords": [],
        "allow_comments": True,
        "version": 1,
        "comment_count": 0,
        "is_pinned": False,
        "view_count": 5,
        "reactions": None,
        "last_comment_at": None,
        "type": "post",
        "citation_count": 0,
        "answer_count": 0,
        "best_answer_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    fake_redis = AsyncMock()
    fake_redis.set.return_value = True  # is_new view

    with (
        patch(
            "app.services.post.post_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=fake_row,
        ),
        patch(
            "app.services.post.post_repo.increment_view_count",
            new_callable=AsyncMock,
        ),
        patch("app.services.post.get_redis", return_value=fake_redis),
        patch("app.services.post.get_pool", return_value=AsyncMock()),
        patch(
            "app.services.post.get_blocked_user_ids",
            new_callable=AsyncMock,
            return_value=set(),
        ),
        patch(
            "app.converters.shared.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await post_service.get_post_by_id(
            post_id, increment_view=True, viewer_id=viewer_id
        )

    assert result is not None
    assert result["view_count"] == 6  # 5 + 1


@pytest.mark.asyncio
async def test_m07_get_post_by_id_no_increment_when_already_viewed():
    """M-07: When viewer already viewed, view_count should stay the same."""
    from app.services import post as post_service

    post_id = uuid.uuid4()
    user_id = uuid.uuid4()
    viewer_id = str(uuid.uuid4())

    fake_row = {
        "id": post_id,
        "title": "Test",
        "content": "Hello",
        "user_id": user_id,
        "author_id": user_id,
        "author_username": "test",
        "author_display_name": "Test User",
        "author_avatar_url": None,
        "category_id": None,
        "category_name": None,
        "sig_id": None,
        "sig_name": None,
        "keywords": [],
        "allow_comments": True,
        "version": 1,
        "comment_count": 0,
        "is_pinned": False,
        "view_count": 5,
        "reactions": None,
        "last_comment_at": None,
        "type": "post",
        "citation_count": 0,
        "answer_count": 0,
        "best_answer_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    fake_redis = AsyncMock()
    fake_redis.set.return_value = False  # already viewed

    with (
        patch(
            "app.services.post.post_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=fake_row,
        ),
        patch("app.services.post.get_redis", return_value=fake_redis),
        patch("app.services.post.get_pool", return_value=AsyncMock()),
        patch(
            "app.services.post.get_blocked_user_ids",
            new_callable=AsyncMock,
            return_value=set(),
        ),
        patch(
            "app.converters.shared.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await post_service.get_post_by_id(
            post_id, increment_view=True, viewer_id=viewer_id
        )

    assert result is not None
    assert result["view_count"] == 5  # unchanged


# ---------------------------------------------------------------------------
# M-09: leave_co_authorship None check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m09_leave_co_authorship_rejects_external_co_author():
    """M-09: External co-authors (user_id=None) should be rejected, not matched via str(None)."""
    from app.core.errors import ForbiddenError
    from app.services import co_author as co_author_service

    co_author_id = uuid.uuid4()
    post_id = uuid.uuid4()

    fake_co_author = {
        "id": co_author_id,
        "post_id": post_id,
        "user_id": None,  # External co-author
    }

    fake_conn = _make_transactional_conn()
    fake_pool = _make_fake_pool(fake_conn)

    with (
        patch("app.services.co_author.get_pool", return_value=fake_pool),
        patch(
            "app.services.co_author.co_author_repo.find_co_author_by_id",
            new_callable=AsyncMock,
            return_value=fake_co_author,
        ),
    ):
        with pytest.raises(ForbiddenError):
            await co_author_service.leave_co_authorship(
                post_id, co_author_id, "None"  # String "None" should NOT match
            )


@pytest.mark.asyncio
async def test_m09_leave_co_authorship_allows_real_user():
    """M-09: Real co-author with matching user_id should succeed."""
    from app.services import co_author as co_author_service

    co_author_id = uuid.uuid4()
    post_id = uuid.uuid4()
    real_user_id = uuid.uuid4()

    fake_co_author = {
        "id": co_author_id,
        "post_id": post_id,
        "user_id": real_user_id,
    }

    fake_conn = _make_transactional_conn()
    fake_pool = _make_fake_pool(fake_conn)

    with (
        patch("app.services.co_author.get_pool", return_value=fake_pool),
        patch(
            "app.services.co_author.co_author_repo.find_co_author_by_id",
            new_callable=AsyncMock,
            return_value=fake_co_author,
        ),
        patch(
            "app.services.co_author.co_author_repo.delete_co_author",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        result = await co_author_service.leave_co_authorship(
            post_id, co_author_id, str(real_user_id)
        )
        assert result is True


# ---------------------------------------------------------------------------
# M-11: Reactions return counts not user lists
# ---------------------------------------------------------------------------


def test_m11_reactions_to_counts():
    """M-11: reactions_to_counts should convert user ID lists to counts."""
    from app.converters.shared import reactions_to_counts

    raw = {"LIKE": ["user1", "user2", "user3"], "SMILE": ["user1"]}
    result = reactions_to_counts(raw)
    assert result == {"LIKE": 3, "SMILE": 1}


def test_m11_reactions_to_counts_none():
    """M-11: reactions_to_counts with None returns None."""
    from app.converters.shared import reactions_to_counts

    assert reactions_to_counts(None) is None


def test_m11_reactions_to_counts_empty():
    """M-11: reactions_to_counts with empty dict returns None."""
    from app.converters.shared import reactions_to_counts

    assert reactions_to_counts({}) is None


def test_m11_fill_user_reactions():
    """M-11: fill_user_reactions should set user_reactions list."""
    from app.converters.shared import fill_user_reactions

    item = {"_raw_reactions": {"LIKE": ["user1", "user2"], "SMILE": ["user1"]}}
    result = fill_user_reactions(item, "user1")
    assert sorted(result["user_reactions"]) == ["LIKE", "SMILE"]


def test_m11_fill_user_reactions_no_viewer():
    """M-11: fill_user_reactions with no viewer should not set user_reactions."""
    from app.converters.shared import fill_user_reactions

    item = {"_raw_reactions": {"LIKE": ["user1"]}}
    result = fill_user_reactions(item, None)
    assert "user_reactions" not in result or result.get("user_reactions") is None


def test_m11_fill_user_reactions_no_match():
    """M-11: fill_user_reactions returns empty list when viewer has no reactions."""
    from app.converters.shared import fill_user_reactions

    item = {"_raw_reactions": {"LIKE": ["user1"]}}
    result = fill_user_reactions(item, "user999")
    assert result["user_reactions"] == []


# ---------------------------------------------------------------------------
# L-06: BulkDeleteNotificationsRequest UUID validation
# ---------------------------------------------------------------------------


def test_l06_notification_ids_rejects_invalid_uuids():
    """L-06: Invalid UUIDs in notification_ids must be rejected."""
    from app.schemas.notification import BulkDeleteNotificationsRequest

    with pytest.raises(ValidationError):
        BulkDeleteNotificationsRequest(notification_ids=["not-a-uuid"])


def test_l06_notification_ids_accepts_valid_uuids():
    """L-06: Valid UUIDs should be accepted."""
    from app.schemas.notification import BulkDeleteNotificationsRequest

    uid = str(uuid.uuid4())
    req = BulkDeleteNotificationsRequest(notification_ids=[uid])
    assert len(req.notification_ids) == 1


def test_l06_notification_ids_accepts_none():
    """L-06: None should be accepted (optional field)."""
    from app.schemas.notification import BulkDeleteNotificationsRequest

    req = BulkDeleteNotificationsRequest(notification_ids=None)
    assert req.notification_ids is None


# ---------------------------------------------------------------------------
# L-07: captcha_code max_length
# ---------------------------------------------------------------------------


def test_l07_captcha_code_max_length():
    """L-07: captcha_code longer than max_length should be rejected."""
    from app.schemas.user import CreateAccountRequest

    with pytest.raises(ValidationError):
        CreateAccountRequest(
            username="testuser",
            password="Pass1234!",
            display_name="Test",
            invite_code="ABC",
            captcha_id="cap1",
            captcha_code="x" * 11,  # max_length=10
        )


def test_l07_captcha_code_valid_length():
    """L-07: captcha_code within max_length should be accepted."""
    from app.schemas.user import CreateAccountRequest

    req = CreateAccountRequest(
        username="testuser",
        password="Pass1234!",
        display_name="Test",
        invite_code="ABC",
        captcha_id="cap1",
        captcha_code="abc123",
    )
    assert req.captcha_code == "abc123"


# ---------------------------------------------------------------------------
# L-10: CSV formula injection pipe char
# ---------------------------------------------------------------------------


def test_l10_csv_sanitize_pipe_char():
    """L-10: Pipe character at start should be prefixed with apostrophe."""
    from app.tasks.form_export import _sanitize_csv_value

    assert _sanitize_csv_value("|cmd") == "'|cmd"


def test_l10_csv_sanitize_normal():
    """L-10: Normal values should pass through unchanged."""
    from app.tasks.form_export import _sanitize_csv_value

    assert _sanitize_csv_value("normal") == "normal"


def test_l10_csv_sanitize_equals():
    """L-10: Equals sign at start should be prefixed."""
    from app.tasks.form_export import _sanitize_csv_value

    assert _sanitize_csv_value("=SUM(A1)") == "'=SUM(A1)"


def test_l10_csv_sanitize_plus():
    """L-10: Plus sign at start should be prefixed."""
    from app.tasks.form_export import _sanitize_csv_value

    assert _sanitize_csv_value("+cmd") == "'+cmd"


def test_l10_csv_sanitize_at():
    """L-10: At sign at start should be prefixed."""
    from app.tasks.form_export import _sanitize_csv_value

    assert _sanitize_csv_value("@evil") == "'@evil"


def test_l10_csv_sanitize_empty():
    """L-10: Empty string should pass through."""
    from app.tasks.form_export import _sanitize_csv_value

    assert _sanitize_csv_value("") == ""


# ---------------------------------------------------------------------------
# L-13: Citation sync uses single query per cited post
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l13_sync_post_citations_single_query_per_cited_post():
    """L-13 + M-06: sync_post_citations should use batch queries, not N+1."""
    from app.services.citation import sync_post_citations

    post_id = uuid.uuid4()
    cited_id = uuid.uuid4()
    author_id = str(uuid.uuid4())
    content = f'<a data-citation="true" href="/posts/{cited_id}">ref</a>'

    fake_conn = _make_transactional_conn()
    # conn.fetch for the batch verification query (ANY($1::uuid[]))
    fake_conn.fetch.return_value = [{"id": cited_id, "user_id": uuid.UUID(author_id)}]
    # conn.executemany for batch INSERT (M-06)
    fake_conn.executemany = AsyncMock()

    fake_pool = _make_fake_pool(fake_conn)

    with (
        patch("app.services.citation.get_pool", return_value=fake_pool),
        patch(
            "app.services.citation.citation_repo.find_existing_citations",
            new_callable=AsyncMock,
            return_value=[],  # No existing citations
        ),
        patch(
            "app.services.citation.citation_repo.update_citation_count",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.citation.parse_cited_post_ids",
            return_value=[cited_id],
        ),
    ):
        await sync_post_citations(post_id, content, author_id)

    # Batch verification: a single conn.fetch call with ANY($1::uuid[])
    fetch_calls = fake_conn.fetch.call_args_list
    verification_queries = [
        c for c in fetch_calls
        if c[0] and isinstance(c[0][0], str)
        and "user_id" in c[0][0]
        and "is_deleted" in c[0][0]
    ]
    assert len(verification_queries) == 1, (
        f"Expected 1 batch verification query, got {len(verification_queries)}"
    )
    sql = verification_queries[0][0][0]
    assert "ANY" in sql  # Batch query uses ANY($1::uuid[])

    # M-06: Batch INSERT via executemany instead of N individual insert_citation calls
    assert fake_conn.executemany.called, "Expected executemany for batch INSERT"


# ---------------------------------------------------------------------------
# L-19: max_respondents validation (cannot lower below current count)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l19_max_respondents_below_current_count():
    """L-19: Cannot lower max_respondents below current response count."""
    from app.core.errors import AppError
    from app.services import form as form_service

    form_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    fake_form = {
        "id": form_id,
        "created_by": uuid.UUID(user_id),
        "is_schema_locked": False,
        "title": "Test Form",
    }

    fake_conn = _make_transactional_conn()
    fake_pool = _make_fake_pool(fake_conn)

    with (
        patch("app.services.form.get_pool", return_value=fake_pool),
        patch(
            "app.services.form.form_repo.find_for_update",
            new_callable=AsyncMock,
            return_value=fake_form,
        ),
        patch(
            "app.services.form.form_repo.count_responses",
            new_callable=AsyncMock,
            return_value=50,  # 50 existing responses
        ),
    ):
        with pytest.raises(AppError) as exc_info:
            await form_service.update_form(
                form_id=form_id,
                user_id=user_id,
                is_admin=False,
                max_respondents=10,  # Below 50 current responses
            )
        assert "max_respondents" in str(exc_info.value.detail).lower() or \
               "response count" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_l19_max_respondents_at_current_count_allowed():
    """L-19: max_respondents equal to current count should be allowed."""
    from app.services import form as form_service

    form_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    fake_form = {
        "id": form_id,
        "created_by": uuid.UUID(user_id),
        "is_schema_locked": False,
        "title": "Test Form",
    }

    fake_conn = _make_transactional_conn()
    fake_pool = _make_fake_pool(fake_conn)

    updated_row = {**fake_form, "questions": "[]", "deadline": None, "max_respondents": 50}

    with (
        patch("app.services.form.get_pool", return_value=fake_pool),
        patch(
            "app.services.form.form_repo.find_for_update",
            new_callable=AsyncMock,
            return_value=fake_form,
        ),
        patch(
            "app.services.form.form_repo.count_responses",
            new_callable=AsyncMock,
            return_value=50,
        ),
        patch(
            "app.services.form.form_repo.update",
            new_callable=AsyncMock,
            return_value=(updated_row, 50),
        ),
        patch(
            "app.services.form.row_to_form",
            return_value=updated_row,
        ),
    ):
        # Should NOT raise -- 50 == 50 is acceptable
        result = await form_service.update_form(
            form_id=form_id,
            user_id=user_id,
            is_admin=False,
            max_respondents=50,
        )
        assert result is not None
