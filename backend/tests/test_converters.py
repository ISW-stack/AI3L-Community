"""Comprehensive tests for all converter modules in app/converters/."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 9, 12, 0, 0, tzinfo=timezone.utc)
_YESTERDAY = _NOW - timedelta(days=1)
_TOMORROW = _NOW + timedelta(days=1)


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _uid_str() -> str:
    return str(uuid.uuid4())


# =========================================================================
# application_converter
# =========================================================================


class TestApplicationConverter:
    """Tests for row_to_application."""

    def _conv(self, row: dict) -> dict:
        from app.converters.application_converter import row_to_application

        return row_to_application(row)

    def _make_row(self, **overrides) -> dict:
        row = {
            "id": _uid(),
            "user_id": _uid(),
            "username": "applicant1",
            "display_name": "Applicant One",
            "description": "I want to join",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": _NOW,
        }
        row.update(overrides)
        return row

    def test_normal_all_fields(self):
        reviewer_id = _uid()
        row = self._make_row(
            reviewed_by=reviewer_id,
            reviewed_at=_YESTERDAY,
            status="APPROVED",
        )
        result = self._conv(row)

        assert result["id"] == str(row["id"])
        assert result["user_id"] == str(row["user_id"])
        assert result["username"] == "applicant1"
        assert result["display_name"] == "Applicant One"
        assert result["description"] == "I want to join"
        assert result["status"] == "APPROVED"
        assert result["reviewed_by"] == str(reviewer_id)
        assert result["reviewed_at"] == _YESTERDAY.isoformat()
        assert result["created_at"] == _NOW.isoformat()

    def test_null_optional_fields(self):
        row = self._make_row()
        result = self._conv(row)

        assert result["reviewed_by"] is None
        assert result["reviewed_at"] is None

    def test_missing_username_display_name(self):
        """username and display_name use .get() so missing keys return None."""
        row = self._make_row()
        del row["username"]
        del row["display_name"]
        result = self._conv(row)

        assert result["username"] is None
        assert result["display_name"] is None

    def test_datetime_isoformat(self):
        row = self._make_row(
            created_at=datetime(2026, 1, 15, 8, 30, 0, tzinfo=timezone.utc)
        )
        result = self._conv(row)
        assert result["created_at"] == "2026-01-15T08:30:00+00:00"

    def test_reviewed_by_zero_uuid(self):
        """reviewed_by with a zero UUID -- UUIDs are always truthy objects."""
        uid = uuid.UUID(int=0)
        row = self._make_row(reviewed_by=uid, reviewed_at=_NOW)
        result = self._conv(row)
        assert result["reviewed_by"] == str(uid)


# =========================================================================
# comment_converter
# =========================================================================


class TestCommentConverter:
    """Tests for row_to_comment."""

    def _conv(self, row: dict) -> dict:
        from app.converters.comment_converter import row_to_comment

        return row_to_comment(row)

    def _make_row(self, **overrides) -> dict:
        row = {
            "id": _uid(),
            "post_id": _uid(),
            "content": "<p>Hello world</p>",
            "author_id": _uid(),
            "author_username": "commenter",
            "author_display_name": "Commenter",
            "author_avatar_url": None,
            "parent_id": None,
            "mentions": None,
            "reactions": None,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        row.update(overrides)
        return row

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/avatar.jpg",
    )
    def test_normal_all_fields(self, mock_presign):
        parent = _uid()
        row = self._make_row(
            author_avatar_url="avatars/pic.jpg",
            parent_id=parent,
            mentions=["user1", "user2"],
            reactions={"like": 3},
        )
        result = self._conv(row)

        assert result["id"] == str(row["id"])
        assert result["post_id"] == str(row["post_id"])
        assert result["content"] == "<p>Hello world</p>"
        assert result["author"]["id"] == str(row["author_id"])
        assert result["author"]["username"] == "commenter"
        assert result["author"]["display_name"] == "Commenter"
        assert result["author"]["avatar_url"] == "https://cdn/avatar.jpg"
        assert result["parent_id"] == str(parent)
        assert result["mentions"] == ["user1", "user2"]
        assert result["reactions"] == {"like": 3}
        assert result["created_at"] == _NOW.isoformat()
        assert result["updated_at"] == _NOW.isoformat()

    def test_null_optional_fields(self):
        row = self._make_row()
        result = self._conv(row)

        assert result["author"]["avatar_url"] is None
        assert result["parent_id"] is None
        assert result["mentions"] is None
        assert result["reactions"] is None

    def test_reactions_json_string(self):
        """asyncpg returns JSONB as string after UPDATE -- converter must parse it."""
        row = self._make_row(reactions='{"thumbsup": 1, "heart": 2}')
        result = self._conv(row)
        assert result["reactions"] == {"thumbsup": 1, "heart": 2}

    def test_reactions_already_dict(self):
        row = self._make_row(reactions={"smile": 5})
        result = self._conv(row)
        assert result["reactions"] == {"smile": 5}

    def test_reactions_empty_json_string(self):
        row = self._make_row(reactions="{}")
        result = self._conv(row)
        assert result["reactions"] == {}

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/a.jpg",
    )
    def test_avatar_url_minio_key_resolved(self, mock_presign):
        row = self._make_row(author_avatar_url="avatars/user123.png")
        result = self._conv(row)
        assert result["author"]["avatar_url"] == "https://cdn/a.jpg"
        mock_presign.assert_called_once_with("avatars/user123.png", expires_in=86400 * 7)

    def test_avatar_url_already_http(self):
        row = self._make_row(author_avatar_url="https://example.com/pic.jpg")
        result = self._conv(row)
        assert result["author"]["avatar_url"] == "https://example.com/pic.jpg"

    def test_avatar_url_http_prefix(self):
        row = self._make_row(author_avatar_url="http://localhost/pic.jpg")
        result = self._conv(row)
        assert result["author"]["avatar_url"] == "http://localhost/pic.jpg"

    def test_datetime_isoformat(self):
        ts = datetime(2025, 12, 25, 0, 0, 0, tzinfo=timezone.utc)
        row = self._make_row(created_at=ts, updated_at=ts)
        result = self._conv(row)
        assert result["created_at"] == "2025-12-25T00:00:00+00:00"
        assert result["updated_at"] == "2025-12-25T00:00:00+00:00"


# =========================================================================
# form_converter
# =========================================================================


class TestFormConverter:
    """Tests for row_to_form with is_active logic."""

    def _conv(self, row: dict, response_count: int = 0) -> dict:
        from app.converters.form_converter import row_to_form

        return row_to_form(row, response_count)

    def _make_row(self, **overrides) -> dict:
        row = {
            "id": _uid(),
            "sig_id": _uid(),
            "title": "Survey A",
            "description": "A survey",
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [{"type": "text", "label": "Name"}],
            "is_schema_locked": False,
            "allow_non_members": False,
            "created_by": _uid(),
            "creator_display_name": "Admin",
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        row.update(overrides)
        return row

    def test_normal_all_fields(self):
        row = self._make_row(
            description="Full survey",
            banner_url="https://img.com/banner.jpg",
            deadline=_TOMORROW,
            max_respondents=100,
            is_schema_locked=True,
            allow_non_members=True,
        )
        result = self._conv(row, response_count=10)

        assert result["id"] == str(row["id"])
        assert result["sig_id"] == str(row["sig_id"])
        assert result["title"] == "Survey A"
        assert result["description"] == "Full survey"
        assert result["banner_url"] == "https://img.com/banner.jpg"
        assert result["deadline"] == _TOMORROW.isoformat()
        assert result["max_respondents"] == 100
        assert result["is_schema_locked"] is True
        assert result["allow_non_members"] is True
        assert result["response_count"] == 10
        assert result["created_by"] == str(row["created_by"])
        assert result["created_by_name"] == "Admin"
        assert result["created_at"] == _NOW.isoformat()
        assert result["updated_at"] == _NOW.isoformat()

    def test_null_optional_fields(self):
        row = self._make_row(
            description=None, banner_url=None, deadline=None, max_respondents=None
        )
        result = self._conv(row)

        assert result["description"] is None
        assert result["banner_url"] is None
        assert result["deadline"] is None
        assert result["max_respondents"] is None

    def test_is_active_no_deadline_no_max(self):
        """No deadline, no max_respondents, not deleted -> active."""
        row = self._make_row()
        result = self._conv(row, response_count=0)
        assert result["is_active"] is True

    def test_is_active_deadline_not_expired(self):
        row = self._make_row(deadline=_TOMORROW)
        result = self._conv(row, response_count=0)
        assert result["is_active"] is True

    def test_is_active_deadline_expired(self):
        row = self._make_row(deadline=_YESTERDAY)
        result = self._conv(row, response_count=0)
        assert result["is_active"] is False

    def test_is_active_max_respondents_not_full(self):
        row = self._make_row(max_respondents=10)
        result = self._conv(row, response_count=5)
        assert result["is_active"] is True

    def test_is_active_max_respondents_full(self):
        row = self._make_row(max_respondents=10)
        result = self._conv(row, response_count=10)
        assert result["is_active"] is False

    def test_is_active_max_respondents_exceeded(self):
        row = self._make_row(max_respondents=5)
        result = self._conv(row, response_count=7)
        assert result["is_active"] is False

    def test_is_active_deleted(self):
        row = self._make_row(is_deleted=True)
        result = self._conv(row, response_count=0)
        assert result["is_active"] is False

    def test_is_active_expired_and_full_and_deleted(self):
        """All three conditions inactive."""
        row = self._make_row(deadline=_YESTERDAY, max_respondents=1, is_deleted=True)
        result = self._conv(row, response_count=5)
        assert result["is_active"] is False

    def test_questions_json_string(self):
        """asyncpg JSONB as string -- must be parsed."""
        qs = [{"type": "rating", "label": "Score"}]
        row = self._make_row(questions=json.dumps(qs))
        result = self._conv(row)
        assert result["questions"] == qs

    def test_questions_already_list(self):
        qs = [{"type": "text", "label": "Name"}]
        row = self._make_row(questions=qs)
        result = self._conv(row)
        assert result["questions"] == qs

    def test_creator_display_name_fallback(self):
        """When creator_display_name is missing, falls back to 'Unknown'."""
        row = self._make_row()
        del row["creator_display_name"]
        result = self._conv(row)
        assert result["created_by_name"] == "Unknown"

    def test_creator_display_name_none(self):
        row = self._make_row(creator_display_name=None)
        result = self._conv(row)
        assert result["created_by_name"] == "Unknown"

    def test_is_schema_locked_default_false(self):
        row = self._make_row()
        del row["is_schema_locked"]
        result = self._conv(row)
        assert result["is_schema_locked"] is False

    def test_allow_non_members_default_false(self):
        row = self._make_row()
        del row["allow_non_members"]
        result = self._conv(row)
        assert result["allow_non_members"] is False

    def test_default_response_count(self):
        row = self._make_row()
        result = self._conv(row)
        assert result["response_count"] == 0


# =========================================================================
# notification_converter
# =========================================================================


class TestNotificationConverter:
    """Tests for row_to_notification."""

    def _conv(self, row: dict) -> dict:
        from app.converters.notification_converter import row_to_notification

        return row_to_notification(row)

    def _make_row(self, **overrides) -> dict:
        row = {
            "id": _uid(),
            "action_type": "COMMENT",
            "entity_type": "post",
            "entity_id": _uid(),
            "message": "User X commented on your post",
            "is_read": False,
            "created_at": _NOW,
            "trigger_user_id": None,
            "trigger_display_name": None,
            "trigger_avatar_url": None,
        }
        row.update(overrides)
        return row

    def test_normal_all_fields_no_trigger_user(self):
        row = self._make_row()
        result = self._conv(row)

        assert result["id"] == str(row["id"])
        assert result["action_type"] == "COMMENT"
        assert result["entity_type"] == "post"
        assert result["entity_id"] == str(row["entity_id"])
        assert result["message"] == "User X commented on your post"
        assert result["is_read"] is False
        assert result["created_at"] == _NOW.isoformat()
        assert result["trigger_user"] is None

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/trig.jpg",
    )
    def test_with_trigger_user(self, mock_presign):
        trigger_uid = _uid()
        row = self._make_row(
            trigger_user_id=trigger_uid,
            trigger_display_name="Trigger User",
            trigger_avatar_url="avatars/trigger.png",
        )
        result = self._conv(row)

        assert result["trigger_user"] is not None
        assert result["trigger_user"]["id"] == str(trigger_uid)
        assert result["trigger_user"]["display_name"] == "Trigger User"
        assert result["trigger_user"]["avatar_url"] == "https://cdn/trig.jpg"

    def test_trigger_user_no_avatar(self):
        trigger_uid = _uid()
        row = self._make_row(
            trigger_user_id=trigger_uid,
            trigger_display_name="No Avatar User",
            trigger_avatar_url=None,
        )
        result = self._conv(row)

        assert result["trigger_user"] is not None
        assert result["trigger_user"]["avatar_url"] is None

    def test_trigger_user_id_without_display_name(self):
        """trigger_user_id present but trigger_display_name is None -> trigger_user is None."""
        row = self._make_row(
            trigger_user_id=_uid(),
            trigger_display_name=None,
        )
        result = self._conv(row)
        assert result["trigger_user"] is None

    def test_trigger_display_name_without_user_id(self):
        """trigger_display_name present but trigger_user_id is None -> trigger_user is None."""
        row = self._make_row(
            trigger_user_id=None,
            trigger_display_name="Ghost",
        )
        result = self._conv(row)
        assert result["trigger_user"] is None

    def test_entity_id_none(self):
        row = self._make_row(entity_id=None)
        result = self._conv(row)
        assert result["entity_id"] is None

    def test_entity_type_none(self):
        row = self._make_row(entity_type=None)
        result = self._conv(row)
        assert result["entity_type"] is None

    def test_is_read_true(self):
        row = self._make_row(is_read=True)
        result = self._conv(row)
        assert result["is_read"] is True

    def test_trigger_user_avatar_http_passthrough(self):
        """Avatar URL starting with http passes through without presigned URL generation."""
        row = self._make_row(
            trigger_user_id=_uid(),
            trigger_display_name="HTTP User",
            trigger_avatar_url="https://gravatar.com/pic.jpg",
        )
        result = self._conv(row)
        assert result["trigger_user"]["avatar_url"] == "https://gravatar.com/pic.jpg"

    def test_trigger_display_name_empty_string(self):
        """Empty string display_name is not None, so trigger_user should be populated."""
        row = self._make_row(
            trigger_user_id=_uid(),
            trigger_display_name="",
        )
        result = self._conv(row)
        # "" is not None, and trigger_user_id is truthy -> trigger_user is set
        assert result["trigger_user"] is not None
        assert result["trigger_user"]["display_name"] == ""


# =========================================================================
# post_converter
# =========================================================================


class TestPostConverter:
    """Tests for row_to_post and row_to_history."""

    def _conv(self, row: dict) -> dict:
        from app.converters.post_converter import row_to_post

        return row_to_post(row)

    def _conv_history(self, row: dict) -> dict:
        from app.converters.post_converter import row_to_history

        return row_to_history(row)

    def _make_row(self, **overrides) -> dict:
        row = {
            "id": _uid(),
            "title": "Test Post",
            "content": "<p>Body</p>",
            "author_id": _uid(),
            "author_username": "author1",
            "author_display_name": "Author One",
            "author_avatar_url": None,
            "category_id": _uid(),
            "category_name": "General",
            "keywords": ["python", "fastapi"],
            "allow_comments": True,
            "version": 1,
            "comment_count": 5,
            "is_pinned": False,
            "view_count": 42,
            "last_comment_at": _NOW,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        row.update(overrides)
        return row

    def test_normal_all_fields(self):
        row = self._make_row()
        result = self._conv(row)

        assert result["id"] == str(row["id"])
        assert result["title"] == "Test Post"
        assert result["content"] == "<p>Body</p>"
        assert result["author"]["id"] == str(row["author_id"])
        assert result["author"]["username"] == "author1"
        assert result["author"]["display_name"] == "Author One"
        assert result["author"]["avatar_url"] is None
        assert result["category_id"] == str(row["category_id"])
        assert result["category_name"] == "General"
        assert result["keywords"] == ["python", "fastapi"]
        assert result["allow_comments"] is True
        assert result["version"] == 1
        assert result["comment_count"] == 5
        assert result["is_pinned"] is False
        assert result["view_count"] == 42
        assert result["last_comment_at"] == _NOW.isoformat()
        assert result["created_at"] == _NOW.isoformat()
        assert result["updated_at"] == _NOW.isoformat()

    def test_null_optional_fields(self):
        row = self._make_row(
            category_id=None,
            category_name=None,
            keywords=None,
            last_comment_at=None,
        )
        result = self._conv(row)

        assert result["category_id"] is None
        assert result["category_name"] is None
        assert result["keywords"] is None
        assert result["last_comment_at"] is None

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/author.jpg",
    )
    def test_author_avatar_resolved(self, mock_presign):
        row = self._make_row(author_avatar_url="avatars/author.png")
        result = self._conv(row)
        assert result["author"]["avatar_url"] == "https://cdn/author.jpg"
        mock_presign.assert_called_once_with("avatars/author.png", expires_in=86400 * 7)

    def test_author_avatar_http_passthrough(self):
        row = self._make_row(author_avatar_url="https://example.com/pic.jpg")
        result = self._conv(row)
        assert result["author"]["avatar_url"] == "https://example.com/pic.jpg"

    def test_is_pinned_default_false(self):
        row = self._make_row()
        del row["is_pinned"]
        result = self._conv(row)
        assert result["is_pinned"] is False

    def test_view_count_default_zero(self):
        row = self._make_row()
        del row["view_count"]
        result = self._conv(row)
        assert result["view_count"] == 0

    def test_last_comment_at_none(self):
        row = self._make_row(last_comment_at=None)
        result = self._conv(row)
        assert result["last_comment_at"] is None

    # --- row_to_history ---

    def test_history_normal(self):
        row = {
            "id": _uid(),
            "version": 3,
            "title": "Revised Title",
            "content": "<p>New content</p>",
            "edited_at": _NOW,
        }
        result = self._conv_history(row)

        assert result["id"] == str(row["id"])
        assert result["version"] == 3
        assert result["title"] == "Revised Title"
        assert result["content"] == "<p>New content</p>"
        assert result["edited_at"] == _NOW.isoformat()

    def test_history_datetime_format(self):
        ts = datetime(2025, 6, 15, 14, 30, 45, tzinfo=timezone.utc)
        row = {
            "id": _uid(),
            "version": 1,
            "title": "V1",
            "content": "body",
            "edited_at": ts,
        }
        result = self._conv_history(row)
        assert result["edited_at"] == "2025-06-15T14:30:45+00:00"


# =========================================================================
# report_converter
# =========================================================================


class TestReportConverter:
    """Tests for row_to_report."""

    def _conv(self, row: dict) -> dict:
        from app.converters.report_converter import row_to_report

        return row_to_report(row)

    def _make_row(self, **overrides) -> dict:
        row = {
            "id": _uid(),
            "post_id": _uid(),
            "user_id": _uid(),
            "reason": "Spam content",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": _NOW,
        }
        row.update(overrides)
        return row

    def test_normal_all_fields(self):
        reviewer = _uid()
        row = self._make_row(
            reviewed_by=reviewer,
            reviewed_at=_NOW,
            status="RESOLVED",
        )
        result = self._conv(row)

        assert result["id"] == str(row["id"])
        assert result["post_id"] == str(row["post_id"])
        assert result["user_id"] == str(row["user_id"])
        assert result["reason"] == "Spam content"
        assert result["status"] == "RESOLVED"
        assert result["reviewed_by"] == str(reviewer)
        assert result["reviewed_at"] == _NOW.isoformat()
        assert result["created_at"] == _NOW.isoformat()

    def test_null_reviewed_fields(self):
        row = self._make_row()
        result = self._conv(row)

        assert result["reviewed_by"] is None
        assert result["reviewed_at"] is None

    def test_post_title_included_when_present(self):
        row = self._make_row(post_title="Offensive Post")
        result = self._conv(row)
        assert result["post_title"] == "Offensive Post"

    def test_post_title_not_included_when_absent(self):
        row = self._make_row()
        result = self._conv(row)
        assert "post_title" not in result

    def test_datetime_isoformat(self):
        ts = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)
        row = self._make_row(created_at=ts, reviewed_at=ts, reviewed_by=_uid())
        result = self._conv(row)
        assert result["created_at"] == "2026-02-28T23:59:59+00:00"
        assert result["reviewed_at"] == "2026-02-28T23:59:59+00:00"


# =========================================================================
# sig_converter
# =========================================================================


class TestSigConverter:
    """Tests for row_to_sig and row_to_member."""

    def _conv_sig(self, row: dict, creator_display_name=None) -> dict:
        from app.converters.sig_converter import row_to_sig

        return row_to_sig(row, creator_display_name)

    def _conv_member(self, row: dict) -> dict:
        from app.converters.sig_converter import row_to_member

        return row_to_member(row)

    def _make_sig_row(self, **overrides) -> dict:
        row = {
            "id": _uid(),
            "name": "NLP Research",
            "description": "Natural Language Processing group",
            "created_by": _uid(),
            "creator_display_name": "Creator",
            "member_count": 15,
            "created_at": _NOW,
        }
        row.update(overrides)
        return row

    def _make_member_row(self, **overrides) -> dict:
        row = {
            "id": _uid(),
            "sig_id": _uid(),
            "user_id": _uid(),
            "role": "MEMBER",
            "display_name": "Member One",
            "username": "member1",
            "avatar_url": None,
            "created_at": _NOW,
        }
        row.update(overrides)
        return row

    # --- row_to_sig ---

    def test_sig_normal(self):
        row = self._make_sig_row()
        result = self._conv_sig(row)

        assert result["id"] == str(row["id"])
        assert result["name"] == "NLP Research"
        assert result["description"] == "Natural Language Processing group"
        assert result["created_by"] == str(row["created_by"])
        assert result["creator_display_name"] == "Creator"
        assert result["member_count"] == 15
        assert result["created_at"] == _NOW.isoformat()

    def test_sig_null_description(self):
        row = self._make_sig_row(description=None)
        result = self._conv_sig(row)
        assert result["description"] is None

    def test_sig_creator_display_name_param_overrides_row(self):
        """When creator_display_name is passed as parameter, it takes precedence."""
        row = self._make_sig_row(creator_display_name="Row Creator")
        result = self._conv_sig(row, creator_display_name="Param Creator")
        assert result["creator_display_name"] == "Param Creator"

    def test_sig_creator_display_name_falls_back_to_row(self):
        """When creator_display_name param is None, uses row value."""
        row = self._make_sig_row(creator_display_name="Row Creator")
        result = self._conv_sig(row, creator_display_name=None)
        assert result["creator_display_name"] == "Row Creator"

    def test_sig_creator_display_name_both_none(self):
        """When both param and row are None."""
        row = self._make_sig_row()
        del row["creator_display_name"]
        result = self._conv_sig(row, creator_display_name=None)
        assert result["creator_display_name"] is None

    # --- row_to_member ---

    def test_member_normal(self):
        row = self._make_member_row()
        result = self._conv_member(row)

        assert result["id"] == str(row["id"])
        assert result["sig_id"] == str(row["sig_id"])
        assert result["user_id"] == str(row["user_id"])
        assert result["role"] == "MEMBER"
        assert result["display_name"] == "Member One"
        assert result["username"] == "member1"
        assert result["avatar_url"] is None
        assert result["created_at"] == _NOW.isoformat()

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/member.jpg",
    )
    def test_member_avatar_resolved(self, mock_presign):
        row = self._make_member_row(avatar_url="avatars/member.png")
        result = self._conv_member(row)
        assert result["avatar_url"] == "https://cdn/member.jpg"
        mock_presign.assert_called_once_with("avatars/member.png", expires_in=86400 * 7)

    def test_member_avatar_http_passthrough(self):
        row = self._make_member_row(avatar_url="https://gravatar.com/x.jpg")
        result = self._conv_member(row)
        assert result["avatar_url"] == "https://gravatar.com/x.jpg"

    def test_member_avatar_none(self):
        row = self._make_member_row(avatar_url=None)
        result = self._conv_member(row)
        assert result["avatar_url"] is None

    def test_member_role_admin(self):
        row = self._make_member_row(role="ADMIN")
        result = self._conv_member(row)
        assert result["role"] == "ADMIN"


# =========================================================================
# user_converter
# =========================================================================


class TestResolveAvatarUrl:
    """Tests for resolve_avatar_url helper function."""

    def _resolve(self, url):
        from app.converters.user_converter import resolve_avatar_url

        return resolve_avatar_url(url)

    def test_none_returns_none(self):
        assert self._resolve(None) is None

    def test_empty_string_returns_none(self):
        assert self._resolve("") is None

    def test_http_url_passthrough(self):
        url = "http://example.com/avatar.jpg"
        assert self._resolve(url) == url

    def test_https_url_passthrough(self):
        url = "https://cdn.example.com/avatar.jpg"
        assert self._resolve(url) == url

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://minio/signed",
    )
    def test_minio_key_generates_presigned(self, mock_presign):
        result = self._resolve("avatars/user123.png")
        assert result == "https://minio/signed"
        mock_presign.assert_called_once_with("avatars/user123.png", expires_in=86400 * 7)

    @patch(
        "app.core.storage.generate_presigned_url",
        side_effect=Exception("MinIO down"),
    )
    def test_presigned_url_exception_returns_key(self, mock_presign):
        """When generate_presigned_url raises, falls back to raw key."""
        result = self._resolve("avatars/broken.png")
        assert result == "avatars/broken.png"


class TestUserToPublicResponse:
    """Tests for user_to_public_response."""

    def _conv(self, user: dict):
        from app.converters.user_converter import user_to_public_response

        return user_to_public_response(user)

    def _make_user(self, **overrides) -> dict:
        user = {
            "id": _uid(),
            "username": "pubuser",
            "display_name": "Public User",
            "role": "MEMBER",
            "avatar_url": None,
            "bio": "A researcher",
            "affiliation": "MIT",
            "orcid": "0000-0001-2345-6789",
            "created_at": _NOW,
        }
        user.update(overrides)
        return user

    def test_normal_all_fields(self):
        user = self._make_user()
        result = self._conv(user)

        assert result.id == str(user["id"])
        assert result.username == "pubuser"
        assert result.display_name == "Public User"
        assert result.role == "MEMBER"
        assert result.avatar_url is None
        assert result.bio == "A researcher"
        assert result.affiliation == "MIT"
        assert result.orcid == "0000-0001-2345-6789"
        assert result.created_at == _NOW.isoformat()

    def test_null_optional_fields(self):
        user = self._make_user(
            avatar_url=None, bio=None, affiliation=None, orcid=None
        )
        result = self._conv(user)

        assert result.avatar_url is None
        assert result.bio is None
        assert result.affiliation is None
        assert result.orcid is None

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/pub.jpg",
    )
    def test_avatar_url_resolved(self, mock_presign):
        user = self._make_user(avatar_url="avatars/pub.png")
        result = self._conv(user)
        assert result.avatar_url == "https://cdn/pub.jpg"

    def test_avatar_http_passthrough(self):
        user = self._make_user(avatar_url="https://example.com/pic.jpg")
        result = self._conv(user)
        assert result.avatar_url == "https://example.com/pic.jpg"

    def test_created_at_already_string(self):
        """created_at can be a string (no .isoformat()) -- converter handles both."""
        user = self._make_user(created_at="2026-01-01T00:00:00+00:00")
        result = self._conv(user)
        assert result.created_at == "2026-01-01T00:00:00+00:00"

    def test_created_at_datetime(self):
        ts = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        user = self._make_user(created_at=ts)
        result = self._conv(user)
        assert result.created_at == "2025-12-31T23:59:59+00:00"

    def test_returns_pydantic_model(self):
        from app.schemas.user import PublicUserResponse

        user = self._make_user()
        result = self._conv(user)
        assert isinstance(result, PublicUserResponse)


class TestUserToResponse:
    """Tests for user_to_response."""

    def _conv(self, user: dict):
        from app.converters.user_converter import user_to_response

        return user_to_response(user)

    def _make_user(self, **overrides) -> dict:
        user = {
            "id": _uid(),
            "username": "fulluser",
            "display_name": "Full User",
            "role": "ADMIN",
            "avatar_url": None,
            "orcid": "0000-0002-3456-7890",
            "affiliation": "Stanford",
            "bio": "Professor",
            "preferred_language": "en",
            "is_banned": False,
            "ban_reason": None,
        }
        user.update(overrides)
        return user

    def test_normal_all_fields(self):
        user = self._make_user()
        result = self._conv(user)

        assert result.id == str(user["id"])
        assert result.username == "fulluser"
        assert result.display_name == "Full User"
        assert result.role == "ADMIN"
        assert result.avatar_url is None
        assert result.orcid == "0000-0002-3456-7890"
        assert result.affiliation == "Stanford"
        assert result.bio == "Professor"
        assert result.preferred_language == "en"
        assert result.is_banned is False
        assert result.ban_reason is None

    def test_null_optional_fields(self):
        user = self._make_user(
            avatar_url=None,
            orcid=None,
            affiliation=None,
            bio=None,
            ban_reason=None,
        )
        result = self._conv(user)

        assert result.avatar_url is None
        assert result.orcid is None
        assert result.affiliation is None
        assert result.bio is None
        assert result.ban_reason is None

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/full.jpg",
    )
    def test_avatar_url_resolved(self, mock_presign):
        user = self._make_user(avatar_url="avatars/full.png")
        result = self._conv(user)
        assert result.avatar_url == "https://cdn/full.jpg"

    def test_avatar_https_passthrough(self):
        user = self._make_user(avatar_url="https://example.com/avatar.jpg")
        result = self._conv(user)
        assert result.avatar_url == "https://example.com/avatar.jpg"

    def test_preferred_language_default(self):
        """When preferred_language is missing, defaults to 'en'."""
        user = self._make_user()
        del user["preferred_language"]
        result = self._conv(user)
        assert result.preferred_language == "en"

    def test_preferred_language_chinese(self):
        user = self._make_user(preferred_language="zh-TW")
        result = self._conv(user)
        assert result.preferred_language == "zh-TW"

    def test_is_banned_default_false(self):
        user = self._make_user()
        del user["is_banned"]
        result = self._conv(user)
        assert result.is_banned is False

    def test_banned_user_with_reason(self):
        user = self._make_user(is_banned=True, ban_reason="Spam")
        result = self._conv(user)
        assert result.is_banned is True
        assert result.ban_reason == "Spam"

    def test_returns_pydantic_model(self):
        from app.schemas.user import UserResponse

        user = self._make_user()
        result = self._conv(user)
        assert isinstance(result, UserResponse)

    def test_role_guest(self):
        user = self._make_user(role="GUEST")
        result = self._conv(user)
        assert result.role == "GUEST"

    def test_role_member(self):
        user = self._make_user(role="MEMBER")
        result = self._conv(user)
        assert result.role == "MEMBER"
