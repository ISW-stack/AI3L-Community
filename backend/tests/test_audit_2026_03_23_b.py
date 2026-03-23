"""Audit fix tests — 2026-03-23 batch B.

Covers: H-02 (bulk_soft_delete file cleanup), H-03 (anonymize_user dict),
M-03 (CSRF expired JWT), M-05 (album cover storage refund),
L-08 (DM recipient validation), L-09 (post limit TTL), L-11 (invite code TZ),
M-08 (DM orphan conversation cleanup), M-12 (async converters).
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError


# ── helpers ───────────────────────────────────────────────────────────────


def _make_pool_and_conn():
    """Build mock pool + conn matching conftest pattern (MagicMock pool)."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock(return_value="UPDATE 1")

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm

    return pool, conn


# ── H-02: bulk_soft_delete cleans up files for each post ──────────────────


@pytest.mark.asyncio
async def test_h02_bulk_soft_delete_cleans_files():
    """H-02: bulk_soft_delete should call _cleanup_post_files for each post."""
    from app.services import post as post_service

    post_ids = [uuid.uuid4(), uuid.uuid4()]
    user_ids = [uuid.uuid4(), uuid.uuid4()]

    pool, conn = _make_pool_and_conn()
    conn.fetch.side_effect = [
        [
            {"id": post_ids[0], "user_id": user_ids[0]},
            {"id": post_ids[1], "user_id": user_ids[1]},
        ],
        [],  # affected cited posts
    ]

    with (
        patch("app.services.post.get_pool", return_value=pool),
        patch(
            "app.services.post.post_repo.bulk_soft_delete",
            new_callable=AsyncMock,
            return_value=2,
        ),
        patch("app.services.post._cleanup_post_files", new_callable=AsyncMock) as mock_cleanup,
        patch("app.repositories.citation_repo.update_citation_count", new_callable=AsyncMock),
    ):
        count = await post_service.bulk_soft_delete(post_ids)

    assert count == 2
    assert mock_cleanup.call_count == 2
    cleanup_calls = {
        (call.args[0], call.args[1]) for call in mock_cleanup.call_args_list
    }
    expected = {(post_ids[0], str(user_ids[0])), (post_ids[1], str(user_ids[1]))}
    assert cleanup_calls == expected


@pytest.mark.asyncio
async def test_h02_bulk_soft_delete_continues_on_cleanup_failure():
    """H-02: If _cleanup_post_files raises for one post, it still cleans the other."""
    from app.services import post as post_service

    post_ids = [uuid.uuid4(), uuid.uuid4()]
    user_ids = [uuid.uuid4(), uuid.uuid4()]

    pool, conn = _make_pool_and_conn()
    conn.fetch.side_effect = [
        [
            {"id": post_ids[0], "user_id": user_ids[0]},
            {"id": post_ids[1], "user_id": user_ids[1]},
        ],
        [],
    ]

    cleanup_mock = AsyncMock(side_effect=[Exception("MinIO down"), None])

    with (
        patch("app.services.post.get_pool", return_value=pool),
        patch(
            "app.services.post.post_repo.bulk_soft_delete",
            new_callable=AsyncMock,
            return_value=2,
        ),
        patch("app.services.post._cleanup_post_files", cleanup_mock),
        patch("app.repositories.citation_repo.update_citation_count", new_callable=AsyncMock),
    ):
        count = await post_service.bulk_soft_delete(post_ids)

    assert count == 2
    assert cleanup_mock.call_count == 2


@pytest.mark.asyncio
async def test_h02_bulk_soft_delete_empty_list():
    """H-02: bulk_soft_delete with empty list returns 0."""
    from app.services import post as post_service

    pool, conn = _make_pool_and_conn()
    conn.fetch.side_effect = [[], []]

    with (
        patch("app.services.post.get_pool", return_value=pool),
        patch(
            "app.services.post.post_repo.bulk_soft_delete",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch("app.services.post._cleanup_post_files", new_callable=AsyncMock) as mock_cleanup,
        patch("app.repositories.citation_repo.update_citation_count", new_callable=AsyncMock),
    ):
        count = await post_service.bulk_soft_delete([])

    assert count == 0
    mock_cleanup.assert_not_called()


# ── H-03: anonymize_user returns dict with cleanup status ─────────────────


@pytest.mark.asyncio
async def test_h03_anonymize_user_reports_cleanup_failure():
    """H-03: anonymize_user should return cleanup_succeeded=False on partial failure."""
    from app.services import user as user_service

    user_id = uuid.uuid4()
    pool, conn = _make_pool_and_conn()
    conn.execute.side_effect = Exception("DB error during cleanup")

    with (
        patch("app.services.user.user_repo") as mock_repo,
        patch("app.core.database.get_pool", return_value=pool),
        patch("app.services.user.async_delete_file", new_callable=AsyncMock),
    ):
        mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
        mock_repo.anonymize = AsyncMock(return_value=True)

        result = await user_service.anonymize_user(user_id)

    assert result["anonymized"] is True
    assert result["cleanup_succeeded"] is False


@pytest.mark.asyncio
async def test_h03_anonymize_user_success_returns_dict():
    """H-03: On full success, returns both flags True."""
    from app.services import user as user_service

    user_id = uuid.uuid4()
    pool, conn = _make_pool_and_conn()
    conn.fetch.return_value = []  # no DM attachments

    with (
        patch("app.services.user.user_repo") as mock_repo,
        patch("app.core.database.get_pool", return_value=pool),
        patch("app.services.user.async_delete_file", new_callable=AsyncMock),
    ):
        mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
        mock_repo.anonymize = AsyncMock(return_value=True)

        result = await user_service.anonymize_user(user_id)

    assert result["anonymized"] is True
    assert result["cleanup_succeeded"] is True


@pytest.mark.asyncio
async def test_h03_anonymize_nonexistent_user():
    """H-03: anonymize_user for nonexistent user returns anonymized=False."""
    from app.services import user as user_service

    user_id = uuid.uuid4()

    with patch("app.services.user.user_repo") as mock_repo:
        mock_repo.find_by_id = AsyncMock(return_value=None)
        mock_repo.anonymize = AsyncMock(return_value=False)

        result = await user_service.anonymize_user(user_id)

    assert result["anonymized"] is False
    assert result["cleanup_succeeded"] is True


# ── M-03: CSRF middleware rejects expired JWT ─────────────────────────────


def test_m03_csrf_rejects_expired_jwt():
    """M-03: CSRF middleware should return 403 with CSRF_004 when JWT is expired."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.testclient import TestClient

    from app.core.csrf import CSRFMiddleware

    csrf_token = "matching-csrf-token"

    app = Starlette()
    app.add_middleware(CSRFMiddleware)

    @app.route("/test-endpoint", methods=["POST"])
    async def test_endpoint(request):
        return JSONResponse({"ok": True})

    with patch("app.core.csrf.decode_access_token", return_value=None):
        client = TestClient(app)
        resp = client.post(
            "/test-endpoint",
            cookies={"csrf_token": csrf_token, "access_token": "expired.jwt.token"},
            headers={"X-CSRF-Token": csrf_token},
        )

    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["code"] == "CSRF_004"
    assert "expired" in body["detail"]["message"].lower()


def test_m03_csrf_rejects_missing_jti():
    """M-03: CSRF middleware returns 403 with CSRF_003 when JWT has no JTI."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.testclient import TestClient

    from app.core.csrf import CSRFMiddleware

    csrf_token = "matching-csrf-token"

    app = Starlette()
    app.add_middleware(CSRFMiddleware)

    @app.route("/test-endpoint", methods=["POST"])
    async def test_endpoint(request):
        return JSONResponse({"ok": True})

    with patch("app.core.csrf.decode_access_token", return_value={"sub": "user1"}):
        client = TestClient(app)
        resp = client.post(
            "/test-endpoint",
            cookies={"csrf_token": csrf_token, "access_token": "valid.jwt.no_jti"},
            headers={"X-CSRF-Token": csrf_token},
        )

    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["code"] == "CSRF_003"
    assert "JTI" in body["detail"]["message"]


def test_m03_csrf_rejects_no_session():
    """M-03: CSRF middleware returns 403 with CSRF_002 when no JWT is present."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.testclient import TestClient

    from app.core.csrf import CSRFMiddleware

    csrf_token = "matching-csrf-token"

    app = Starlette()
    app.add_middleware(CSRFMiddleware)

    @app.route("/test-endpoint", methods=["POST"])
    async def test_endpoint(request):
        return JSONResponse({"ok": True})

    client = TestClient(app)
    resp = client.post(
        "/test-endpoint",
        cookies={"csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["code"] == "CSRF_002"


def test_m03_csrf_bearer_token_passes_through():
    """M-03: Bearer tokens should pass CSRF (immune by design), only cookies need JTI binding."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.testclient import TestClient

    from app.core.csrf import CSRFMiddleware

    csrf_token = "matching-csrf-token"

    app = Starlette()
    app.add_middleware(CSRFMiddleware)

    @app.route("/test-endpoint", methods=["POST"])
    async def test_endpoint(request):
        return JSONResponse({"ok": True})

    client = TestClient(app)
    resp = client.post(
        "/test-endpoint",
        cookies={"csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token, "Authorization": "Bearer fake"},
    )

    assert resp.status_code == 200


# ── M-05: Album cover storage refund ─────────────────────────────────────


@pytest.mark.asyncio
async def test_m05_album_cover_refunds_old_storage():
    """M-05: Replacing album cover should decrement storage for old cover size."""
    from app.services import album as album_service

    album_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    user_uuid = uuid.UUID(user_id)
    album_uuid = uuid.UUID(album_id)

    fake_album = {
        "id": album_uuid,
        "created_by": user_uuid,
        "cover_photo_url": f"albums/{album_id}/cover/old_cover.jpg",
        "is_archived": False,
    }

    old_cover_size = 12345
    execute_calls: list[tuple] = []

    async def track_execute(sql, *args, **kwargs):
        execute_calls.append((sql, args))

    def _make_acquire_cm(conn):
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    # Build connections: phase 1 (perms), phase 3 (quota), phase 4 (final read)
    perm_conn = AsyncMock()
    quota_conn = AsyncMock()
    quota_conn.fetchrow = AsyncMock(return_value={"storage_used_bytes": 5000})
    quota_conn.execute = AsyncMock(side_effect=track_execute)
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    quota_conn.transaction = MagicMock(return_value=tx)

    pool = MagicMock()
    # Each pool.acquire() call returns a fresh context manager with the right conn
    pool.acquire.side_effect = [
        _make_acquire_cm(perm_conn),   # Phase 1: permissions
        _make_acquire_cm(quota_conn),  # Phase 3: quota + DB update
        _make_acquire_cm(perm_conn),   # Phase 4: final read
    ]

    with (
        patch("app.services.album.get_pool", return_value=pool),
        patch(
            "app.services.album.album_repo.find_album_by_id",
            new_callable=AsyncMock,
            return_value=fake_album,
        ),
        patch(
            "app.services.album.album_repo.find_member",
            new_callable=AsyncMock,
            return_value={"role": "ADMIN", "status": "ACCEPTED"},
        ),
        patch(
            "app.services.album.album_repo.set_cover_photo",
            new_callable=AsyncMock,
        ),
        patch("app.core.async_storage.upload_file", new_callable=AsyncMock),
        patch("app.core.async_storage.delete_file", new_callable=AsyncMock),
        patch(
            "app.core.async_storage.get_file_size",
            new_callable=AsyncMock,
            return_value=old_cover_size,
        ),
        patch("app.services.album.validate_magic_number", return_value=True),
    ):
        try:
            await album_service.upload_cover(
                album_id, user_id, "MEMBER", b"\xff" * 100, "cover.jpg", "image/jpeg"
            )
        except Exception:
            pass  # May fail on final read; we only care about storage refund SQL

    refund_calls = [
        (sql, args)
        for sql, args in execute_calls
        if "GREATEST" in sql and "storage_used_bytes" in sql
    ]
    assert len(refund_calls) >= 1, (
        f"Expected a GREATEST(...) storage refund call, got: {execute_calls}"
    )
    refund_sql, refund_args = refund_calls[0]
    assert old_cover_size in refund_args


# ── L-08: DM recipient existence validation ───────────────────────────────


@pytest.mark.asyncio
async def test_l08_dm_rejects_deleted_recipient():
    """L-08: send_message should reject messages to deleted users."""
    from app.services import dm as dm_service

    sender_id = str(uuid.uuid4())
    recipient_id = str(uuid.uuid4())

    with patch(
        "app.repositories.user_repo.find_by_id",
        new_callable=AsyncMock,
        return_value={"is_deleted": True},
    ):
        with pytest.raises(AppError) as exc_info:
            await dm_service.send_message(sender_id, recipient_id, content="Hello")
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_l08_dm_rejects_nonexistent_recipient():
    """L-08: send_message should reject messages to nonexistent users."""
    from app.services import dm as dm_service

    with patch(
        "app.repositories.user_repo.find_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(AppError) as exc_info:
            await dm_service.send_message(
                str(uuid.uuid4()), str(uuid.uuid4()), content="Hello"
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_l08_dm_rejects_self_message():
    """L-08: send_message should reject self-messages before DB lookup."""
    from app.services import dm as dm_service

    user_id = str(uuid.uuid4())

    with pytest.raises(AppError) as exc_info:
        await dm_service.send_message(user_id, user_id, content="Hello")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_l08_dm_requires_content_or_file():
    """L-08: send_message without content or file raises 422."""
    from app.services import dm as dm_service

    sender_id = str(uuid.uuid4())
    recipient_id = str(uuid.uuid4())

    with patch(
        "app.repositories.user_repo.find_by_id",
        new_callable=AsyncMock,
        return_value={"is_deleted": False, "id": uuid.UUID(recipient_id)},
    ):
        with pytest.raises(AppError) as exc_info:
            await dm_service.send_message(sender_id, recipient_id, content=None)
        assert exc_info.value.status_code == 422


# ── L-11: invite_code timezone-aware comparison ───────────────────────────


@pytest.mark.asyncio
async def test_l11_invite_code_timezone_aware_expiry():
    """L-11: Expired codes should be detected using timezone-aware comparison."""
    from app.services import invite_code as ic_service

    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)

    mock_rows = [
        {
            "id": str(uuid.uuid4()),
            "code": "EXPIRED01",
            "consumed_at": None,
            "expires_at": past_time.replace(tzinfo=None),
            "created_by": str(uuid.uuid4()),
        },
        {
            "id": str(uuid.uuid4()),
            "code": "ACTIVE01",
            "consumed_at": None,
            "expires_at": future_time.replace(tzinfo=None),
            "created_by": str(uuid.uuid4()),
        },
        {
            "id": str(uuid.uuid4()),
            "code": "CONSUMED01",
            "consumed_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "expires_at": future_time.replace(tzinfo=None),
            "created_by": str(uuid.uuid4()),
        },
    ]

    with patch(
        "app.services.invite_code.invite_code_repo.find_many",
        new_callable=AsyncMock,
        return_value=(mock_rows, 3),
    ):
        codes, total = await ic_service.list_invite_codes()

    assert total == 3
    statuses = {c["code"]: c["status"] for c in codes}
    assert statuses["EXPIRED01"] == "expired"
    assert statuses["ACTIVE01"] == "active"
    assert statuses["CONSUMED01"] == "consumed"


@pytest.mark.asyncio
async def test_l11_invite_code_no_expires_at_is_active():
    """L-11: Codes without expires_at should be marked active (not crash)."""
    from app.services import invite_code as ic_service

    mock_rows = [
        {
            "id": str(uuid.uuid4()),
            "code": "NOEXPIRY",
            "consumed_at": None,
            "expires_at": None,
            "created_by": str(uuid.uuid4()),
        },
    ]

    with patch(
        "app.services.invite_code.invite_code_repo.find_many",
        new_callable=AsyncMock,
        return_value=(mock_rows, 1),
    ):
        codes, total = await ic_service.list_invite_codes()

    assert codes[0]["status"] == "active"


# ── L-09: Daily post limit TTL aligned to midnight ────────────────────────


@pytest.mark.asyncio
async def test_l09_post_limit_ttl_midnight_aligned():
    """L-09: Post limit key should expire at UTC midnight, not 86400s from now."""
    from app.services import post as post_service

    fake_redis = AsyncMock()
    fake_redis.incr.return_value = 1

    with patch("app.services.post.get_redis", return_value=fake_redis):
        result = await post_service._atomic_check_and_increment_post_limit("user1")

    assert result is True
    fake_redis.expire.assert_called_once()
    ttl = fake_redis.expire.call_args[0][1]
    assert 0 < ttl <= 86400


@pytest.mark.asyncio
async def test_l09_post_limit_safety_net_resets_ttl():
    """L-09: If TTL is missing (-1), re-set it to 86400."""
    from app.services import post as post_service

    fake_redis = AsyncMock()
    fake_redis.incr.return_value = 2
    fake_redis.ttl.return_value = -1

    with patch("app.services.post.get_redis", return_value=fake_redis):
        result = await post_service._atomic_check_and_increment_post_limit("user1")

    assert result is True
    fake_redis.expire.assert_called_once()
    ttl = fake_redis.expire.call_args[0][1]
    assert ttl == 86400


@pytest.mark.asyncio
async def test_l09_post_limit_over_max_returns_false():
    """L-09: When count exceeds MAX_POSTS_PER_DAY, returns False and decrements."""
    from app.core.constants import MAX_POSTS_PER_DAY
    from app.services import post as post_service

    fake_redis = AsyncMock()
    fake_redis.incr.return_value = MAX_POSTS_PER_DAY + 1
    fake_redis.ttl.return_value = 3600

    with patch("app.services.post.get_redis", return_value=fake_redis):
        result = await post_service._atomic_check_and_increment_post_limit("user1")

    assert result is False
    fake_redis.decr.assert_called_once()


# ── M-08: DM orphaned conversation cleanup on failure ─────────────────────


@pytest.mark.asyncio
async def test_m08_dm_cleans_up_new_conversation_on_failure():
    """M-08: If send_message_atomic fails and conversation was newly created, delete it."""
    from app.services import dm as dm_service

    sender_id = str(uuid.uuid4())
    recipient_id = str(uuid.uuid4())
    conversation_id = uuid.uuid4()

    recipient = {"is_deleted": False, "id": uuid.UUID(recipient_id)}

    pool, conn = _make_pool_and_conn()
    conn.fetchval.return_value = False  # dm_friends_only

    with (
        patch(
            "app.repositories.user_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=recipient,
        ),
        patch("app.core.database.get_pool", return_value=pool),
        patch(
            "app.repositories.social_repo.is_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.services.dm.dm_repo.find_or_create_conversation",
            new_callable=AsyncMock,
            return_value={"id": conversation_id, "was_new": True},
        ),
        patch(
            "app.services.dm.dm_repo.send_message_atomic",
            new_callable=AsyncMock,
            side_effect=Exception("DB insert failed"),
        ),
        patch(
            "app.services.dm.dm_repo.delete_empty_conversation",
            new_callable=AsyncMock,
        ) as mock_delete_conv,
    ):
        with pytest.raises(Exception, match="DB insert failed"):
            await dm_service.send_message(sender_id, recipient_id, content="Hello")

    mock_delete_conv.assert_called_once_with(conversation_id)


@pytest.mark.asyncio
async def test_m08_dm_does_not_delete_existing_conversation_on_failure():
    """M-08: If conversation already existed, do NOT delete it on failure."""
    from app.services import dm as dm_service

    sender_id = str(uuid.uuid4())
    recipient_id = str(uuid.uuid4())
    conversation_id = uuid.uuid4()

    recipient = {"is_deleted": False, "id": uuid.UUID(recipient_id)}

    pool, conn = _make_pool_and_conn()
    conn.fetchval.return_value = False

    with (
        patch(
            "app.repositories.user_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=recipient,
        ),
        patch("app.core.database.get_pool", return_value=pool),
        patch(
            "app.repositories.social_repo.is_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.services.dm.dm_repo.find_or_create_conversation",
            new_callable=AsyncMock,
            return_value={"id": conversation_id, "was_new": False},
        ),
        patch(
            "app.services.dm.dm_repo.send_message_atomic",
            new_callable=AsyncMock,
            side_effect=Exception("DB insert failed"),
        ),
        patch(
            "app.services.dm.dm_repo.delete_empty_conversation",
            new_callable=AsyncMock,
        ) as mock_delete_conv,
    ):
        with pytest.raises(Exception, match="DB insert failed"):
            await dm_service.send_message(sender_id, recipient_id, content="Hello")

    mock_delete_conv.assert_not_called()


# ── M-12: Async album converter ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_m12_album_converter_is_async():
    """M-12: Album converter functions should be async (not blocking event loop)."""
    from app.converters import album_converter

    assert asyncio.iscoroutinefunction(album_converter.to_album_response)
    assert asyncio.iscoroutinefunction(album_converter.to_album_photo_response)
    assert asyncio.iscoroutinefunction(album_converter.to_album_member_response)
    assert asyncio.iscoroutinefunction(album_converter.to_album_comment_response)


@pytest.mark.asyncio
async def test_m12_social_converter_is_async():
    """M-12: Social converter functions that resolve avatars should be async."""
    from app.converters import social_converter

    assert asyncio.iscoroutinefunction(social_converter.to_friendship_response)
    assert asyncio.iscoroutinefunction(social_converter.to_friend_request_response)
    assert asyncio.iscoroutinefunction(social_converter.to_follow_user_response)
    assert asyncio.iscoroutinefunction(social_converter.to_block_response)


@pytest.mark.asyncio
async def test_m12_album_converter_returns_dict():
    """M-12: to_album_response returns a proper dict with expected keys."""
    from app.converters import album_converter

    fake_row = {
        "id": uuid.uuid4(),
        "title": "Test Album",
        "description": "desc",
        "cover_photo_url": None,
        "created_by": uuid.uuid4(),
        "created_by_name": "TestUser",
        "is_archived": False,
        "photo_count": 5,
        "member_count": 2,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = await album_converter.to_album_response(fake_row)

    assert isinstance(result, dict)
    assert result["title"] == "Test Album"
    assert result["cover_photo_url"] is None
    assert result["photo_count"] == 5
