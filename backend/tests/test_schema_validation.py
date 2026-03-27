"""Tests for schema-level validation (role, input bounds, patterns)."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import GuestLoginRequest, LoginRequest
from app.schemas.citation import CitationSearchRequest
from app.schemas.comment import CommentCreateRequest
from app.schemas.form import (
    FormCreateRequest,
    FormUpdateRequest,
    QuestionOption,
    QuestionSchema,
)
from app.schemas.notification import BulkDeleteNotificationsRequest
from app.schemas.post import PostCreateRequest, PostUpdateRequest
from app.schemas.social import FriendRequestCreateRequest
from app.schemas.user import (
    AdminCreateAccountRequest,
    ApplyMemberRequest,
    ChangePasswordRequest,
    CreateAccountRequest,
    RoleUpdateRequest,
    UserUpdateRequest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_create_account(**overrides):
    defaults = {
        "username": "valid_user",
        "password": "Test1234!",
        "display_name": "Test User",
        "invite_code": "abc123",
        "captcha_id": "cap1",
        "captcha_code": "1234",
    }
    defaults.update(overrides)
    return CreateAccountRequest(**defaults)


def _valid_apply_member(**overrides):
    defaults = {
        "username": "valid_user",
        "password": "Test1234!",
        "display_name": "Test User",
        "description": "I want to join",
    }
    defaults.update(overrides)
    return ApplyMemberRequest(**defaults)


def _valid_admin_create(**overrides):
    defaults = {
        "username": "valid_user",
        "password": "Test1234!",
        "display_name": "Test User",
    }
    defaults.update(overrides)
    return AdminCreateAccountRequest(**defaults)


def _minimal_question(**overrides):
    defaults = {
        "id": "q1",
        "type": "text",
        "label": "Question 1",
    }
    defaults.update(overrides)
    return QuestionSchema(**defaults)


def _valid_form_create(**overrides):
    defaults = {
        "title": "My Form",
        "questions": [_minimal_question()],
    }
    defaults.update(overrides)
    # questions may be dicts or QuestionSchema; convert dicts
    if "questions" in defaults and defaults["questions"]:
        qs = []
        for q in defaults["questions"]:
            if isinstance(q, dict):
                qs.append(QuestionSchema(**q))
            else:
                qs.append(q)
        defaults["questions"] = qs
    return FormCreateRequest(**defaults)


class TestRoleUpdateRequestValidation:
    def test_valid_roles(self):
        for role in ["SUPER_ADMIN", "ADMIN", "MEMBER"]:
            req = RoleUpdateRequest(role=role)
            assert req.role == role

    def test_guest_rejected(self):
        with pytest.raises(ValidationError):
            RoleUpdateRequest(role="GUEST")

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            RoleUpdateRequest(role="INVALID")

    def test_empty_role_rejected(self):
        with pytest.raises(ValidationError):
            RoleUpdateRequest(role="")

    def test_lowercase_rejected(self):
        with pytest.raises(ValidationError):
            RoleUpdateRequest(role="admin")


class TestAdminCreateAccountRequestValidation:
    def test_valid_roles(self):
        for role in ["MEMBER", "ADMIN"]:
            req = AdminCreateAccountRequest(
                username="testuser",
                password="P@ssword1!",
                display_name="Test",
                role=role,
            )
            assert req.role == role

    def test_default_role_is_member(self):
        req = AdminCreateAccountRequest(
            username="testuser", password="P@ssword1!", display_name="Test"
        )
        assert req.role == "MEMBER"

    def test_super_admin_rejected(self):
        with pytest.raises(ValidationError):
            AdminCreateAccountRequest(
                username="testuser",
                password="P@ssword1!",
                display_name="Test",
                role="SUPER_ADMIN",
            )

    def test_guest_rejected(self):
        with pytest.raises(ValidationError):
            AdminCreateAccountRequest(
                username="testuser",
                password="P@ssword1!",
                display_name="Test",
                role="GUEST",
            )

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            AdminCreateAccountRequest(
                username="testuser",
                password="P@ssword1!",
                display_name="Test",
                role="INVALID",
            )


# ===========================================================================
# H-07: Username character whitelist
# ===========================================================================


class TestUsernamePattern:
    @pytest.mark.parametrize(
        "username",
        ["alice", "Bob_123", "user-name", "abc", "a" * 50, "user@name", "user.name", "leo@gmail.com"],
    )
    def test_valid_usernames(self, username):
        _valid_create_account(username=username)

    @pytest.mark.parametrize(
        "username",
        [
            "user name",  # space
            "\u0430dmin",  # Cyrillic 'a' (homograph)
            "user\u200bname",  # zero-width space
            "admin!",  # exclamation
            "user/name",  # slash
        ],
    )
    def test_invalid_usernames_rejected(self, username):
        with pytest.raises(ValidationError):
            _valid_create_account(username=username)

    def test_apply_member_username_pattern(self):
        with pytest.raises(ValidationError):
            _valid_apply_member(username="bad user")

    def test_admin_create_username_pattern(self):
        with pytest.raises(ValidationError):
            _valid_admin_create(username="bad!user")


# ===========================================================================
# M-26: PostCreateRequest.content max_length
# ===========================================================================


class TestPostContentMaxLength:
    def test_content_within_limit(self):
        PostCreateRequest(title="t", content="x" * 100_000)

    def test_content_exceeds_limit(self):
        with pytest.raises(ValidationError):
            PostCreateRequest(title="t", content="x" * 100_001)

    def test_update_content_exceeds_limit(self):
        with pytest.raises(ValidationError):
            PostUpdateRequest(content="x" * 100_001, version=1)


# ===========================================================================
# M-27: ChangePasswordRequest bounded
# ===========================================================================


class TestChangePasswordMaxLength:
    def test_current_password_too_long(self):
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="x" * 129,
                new_password="Valid123!",
            )

    def test_new_password_too_long(self):
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="old",
                new_password="x" * 129,
            )

    def test_valid_passwords(self):
        ChangePasswordRequest(
            current_password="x" * 128,
            new_password="x" * 128,
        )


# ===========================================================================
# M-28: FormCreateRequest.questions max_length
# ===========================================================================


class TestFormQuestionsMaxLength:
    def test_questions_within_limit(self):
        qs = [_minimal_question(id=f"q{i}") for i in range(100)]
        FormCreateRequest(title="Form", questions=qs)

    def test_questions_exceeds_limit(self):
        qs = [_minimal_question(id=f"q{i}") for i in range(101)]
        with pytest.raises(ValidationError):
            FormCreateRequest(title="Form", questions=qs)

    def test_update_questions_exceeds_limit(self):
        qs = [_minimal_question(id=f"q{i}") for i in range(101)]
        with pytest.raises(ValidationError):
            FormUpdateRequest(questions=qs)


# ===========================================================================
# M-29: QuestionSchema field bounds
# ===========================================================================


class TestQuestionSchemaBounds:
    def test_question_id_too_long(self):
        with pytest.raises(ValidationError):
            _minimal_question(id="x" * 101)

    def test_question_label_too_long(self):
        with pytest.raises(ValidationError):
            _minimal_question(label="x" * 501)

    def test_option_id_too_long(self):
        with pytest.raises(ValidationError):
            QuestionOption(id="x" * 101, label="opt")

    def test_option_label_too_long(self):
        with pytest.raises(ValidationError):
            QuestionOption(label="x" * 501, id="o1")

    def test_max_length_bounds(self):
        _minimal_question(max_length=1)
        _minimal_question(max_length=10000)
        with pytest.raises(ValidationError):
            _minimal_question(max_length=0)
        with pytest.raises(ValidationError):
            _minimal_question(max_length=10001)

    def test_min_bounds(self):
        _minimal_question(min=0)
        _minimal_question(min=100)
        with pytest.raises(ValidationError):
            _minimal_question(min=-1)
        with pytest.raises(ValidationError):
            _minimal_question(min=101)

    def test_max_bounds(self):
        _minimal_question(max=1)
        _minimal_question(max=100)
        with pytest.raises(ValidationError):
            _minimal_question(max=0)
        with pytest.raises(ValidationError):
            _minimal_question(max=101)

    def test_max_size_mb_bounds(self):
        _minimal_question(max_size_mb=1)
        _minimal_question(max_size_mb=50)
        with pytest.raises(ValidationError):
            _minimal_question(max_size_mb=0)
        with pytest.raises(ValidationError):
            _minimal_question(max_size_mb=51)

    def test_options_list_max_length(self):
        opts = [QuestionOption(id=f"o{i}", label=f"Option {i}") for i in range(51)]
        with pytest.raises(ValidationError):
            _minimal_question(type="single_choice", options=opts)

    def test_allowed_types_max_length(self):
        types_list = [f"type{i}" for i in range(21)]
        with pytest.raises(ValidationError):
            _minimal_question(type="file_upload", allowed_types=types_list)


# ===========================================================================
# M-30: CommentCreateRequest.mentions max
# ===========================================================================


class TestMentionsMax:
    def test_mentions_within_limit(self):
        CommentCreateRequest(content="hello", mentions=["u"] * 20)

    def test_mentions_exceeds_limit(self):
        with pytest.raises(ValidationError):
            CommentCreateRequest(content="hello", mentions=["u"] * 21)


# ===========================================================================
# M-32: FormCreateRequest.banner_url validation
# ===========================================================================


class TestBannerUrlValidation:
    def test_valid_http_url(self):
        _valid_form_create(banner_url="http://example.com/banner.png")

    def test_valid_https_url(self):
        _valid_form_create(banner_url="https://example.com/banner.png")

    def test_javascript_url_rejected(self):
        with pytest.raises(ValidationError):
            _valid_form_create(banner_url="javascript:alert(1)")

    def test_data_url_rejected(self):
        with pytest.raises(ValidationError):
            _valid_form_create(banner_url="data:text/html,<script>alert(1)</script>")

    def test_ftp_url_rejected(self):
        with pytest.raises(ValidationError):
            _valid_form_create(banner_url="ftp://evil.com/file")

    def test_banner_url_too_long(self):
        with pytest.raises(ValidationError):
            _valid_form_create(banner_url="https://example.com/" + "x" * 2000)

    def test_update_banner_url_rejected(self):
        with pytest.raises(ValidationError):
            FormUpdateRequest(banner_url="javascript:void(0)")

    def test_none_banner_url_ok(self):
        _valid_form_create(banner_url=None)


# ===========================================================================
# M-33: display_name rejects control/zero-width chars
# ===========================================================================


class TestDisplayNameValidation:
    @pytest.mark.parametrize(
        "name",
        [
            "Alice",
            "Bob Smith",
            "\u5f20\u4e09",  # Chinese characters
            "Ren\u00e9",  # accented Latin
            "\u7530\u4e2d\u592a\u90ce",  # Japanese
            "Dr. Test (PhD)",
        ],
    )
    def test_valid_display_names(self, name):
        _valid_create_account(display_name=name)

    @pytest.mark.parametrize(
        "char,desc",
        [
            ("\x00", "null byte"),
            ("\x1f", "control char"),
            ("\u200b", "zero-width space"),
            ("\u200c", "zero-width non-joiner"),
            ("\u200d", "zero-width joiner"),
            ("\u202e", "RTL override"),
            ("\ufeff", "BOM"),
        ],
    )
    def test_control_chars_rejected(self, char, desc):
        with pytest.raises(ValidationError, match="control characters"):
            _valid_create_account(display_name=f"admin{char}")

    def test_apply_member_display_name_validation(self):
        with pytest.raises(ValidationError):
            _valid_apply_member(display_name="bad\x00name")

    def test_admin_create_display_name_validation(self):
        with pytest.raises(ValidationError):
            _valid_admin_create(display_name="bad\u200bname")

    def test_guest_login_display_name_validation(self):
        with pytest.raises(ValidationError):
            GuestLoginRequest(
                display_name="evil\u202ename",
                captcha_id="c1",
                captcha_code="1234",
            )

    def test_user_update_display_name_validation(self):
        with pytest.raises(ValidationError):
            UserUpdateRequest(display_name="bad\x01name")

    def test_user_update_none_display_name_ok(self):
        UserUpdateRequest(display_name=None)


# ===========================================================================
# L-31: CitationSearchRequest bounds
# ===========================================================================


class TestCitationSearchBounds:
    def test_query_too_long(self):
        with pytest.raises(ValidationError):
            CitationSearchRequest(query="x" * 201)

    def test_query_empty(self):
        with pytest.raises(ValidationError):
            CitationSearchRequest(query="")

    def test_limit_too_high(self):
        with pytest.raises(ValidationError):
            CitationSearchRequest(query="test", limit=51)

    def test_limit_too_low(self):
        with pytest.raises(ValidationError):
            CitationSearchRequest(query="test", limit=0)

    def test_valid_citation_search(self):
        CitationSearchRequest(query="machine learning", limit=25)


# ===========================================================================
# L-32: BulkDeleteNotificationsRequest max_length
# ===========================================================================


class TestNotificationBulkDeleteMax:
    def test_within_limit(self):
        BulkDeleteNotificationsRequest(notification_ids=["id"] * 100)

    def test_exceeds_limit(self):
        with pytest.raises(ValidationError):
            BulkDeleteNotificationsRequest(notification_ids=["id"] * 101)


# ===========================================================================
# L-33: PostCreateRequest UUID pattern for category_id / sig_id
# ===========================================================================


class TestPostUuidPatternValidation:
    VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"

    def test_valid_category_id(self):
        PostCreateRequest(title="t", content="c", category_id=self.VALID_UUID)

    def test_invalid_category_id(self):
        with pytest.raises(ValidationError):
            PostCreateRequest(title="t", content="c", category_id="not-a-uuid")

    def test_valid_sig_id(self):
        PostCreateRequest(title="t", content="c", sig_id=self.VALID_UUID)

    def test_invalid_sig_id(self):
        with pytest.raises(ValidationError):
            PostCreateRequest(title="t", content="c", sig_id="not-a-uuid")

    def test_none_ids_ok(self):
        PostCreateRequest(title="t", content="c")


# ===========================================================================
# L-34: FriendRequestCreateRequest UUID pattern
# ===========================================================================


class TestFriendRequestUuidPattern:
    def test_valid_uuid(self):
        FriendRequestCreateRequest(user_id="550e8400-e29b-41d4-a716-446655440000")

    def test_invalid_uuid(self):
        with pytest.raises(ValidationError):
            FriendRequestCreateRequest(user_id="not-a-uuid")

    def test_uppercase_uuid_rejected(self):
        with pytest.raises(ValidationError):
            FriendRequestCreateRequest(user_id="550E8400-E29B-41D4-A716-446655440000")


# ===========================================================================
# L-35: captcha_id max_length
# ===========================================================================


class TestCaptchaIdMaxLength:
    def test_create_account_captcha_id_too_long(self):
        with pytest.raises(ValidationError):
            _valid_create_account(captcha_id="x" * 101)

    def test_login_captcha_id_too_long(self):
        with pytest.raises(ValidationError):
            LoginRequest(
                username="user",
                password="pass",
                captcha_id="x" * 101,
                captcha_code="1234",
            )

    def test_guest_login_captcha_id_too_long(self):
        with pytest.raises(ValidationError):
            GuestLoginRequest(
                display_name="guest",
                captcha_id="x" * 101,
                captcha_code="1234",
            )

    def test_captcha_id_within_limit(self):
        LoginRequest(
            username="user",
            password="pass",
            captcha_id="x" * 100,
            captcha_code="1234",
        )
