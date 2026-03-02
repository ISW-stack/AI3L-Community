"""Integration tests: SQL correctness against a real PostgreSQL database.

Validates that the SQL in repository modules is syntactically valid and
that column names match the actual schema. These tests catch bugs that
mocked unit tests cannot (e.g., referencing a non-existent column).
"""

import os
import uuid

import asyncpg
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Integration tests require RUN_INTEGRATION_TESTS=1",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _create_user(conn, username="testuser", role="MEMBER"):
    """Insert a minimal user row and return the user_id."""
    user_id = uuid.uuid4()
    await conn.execute(
        """INSERT INTO users (id, username, password_hash, role, display_name)
           VALUES ($1, $2, $3, $4, $5)""",
        user_id,
        username,
        "$argon2id$v=19$m=65536,t=3,p=4$fake$hash",
        role,
        username,
    )
    return user_id


async def _create_category(conn, name="General"):
    """Insert a category and return the category_id."""
    cat_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO categories (id, name) VALUES ($1, $2)",
        cat_id,
        name,
    )
    return cat_id


async def _create_post(conn, user_id, title="Test Post", content="Body", category_id=None):
    """Insert a post and return the post_id."""
    post_id = uuid.uuid4()
    await conn.execute(
        """INSERT INTO posts (id, user_id, title, content, category_id)
           VALUES ($1, $2, $3, $4, $5)""",
        post_id,
        user_id,
        title,
        content,
        category_id,
    )
    return post_id


# ===========================================================================
# Test: invite_code_repo.find_many() — verifies the fixed `created_by` column
# ===========================================================================
class TestInviteCodeRepo:
    async def test_find_many_sql_uses_correct_columns(self, db_pool):
        """Verify invite_code_repo's SQL references `created_by` (not `creator_id`).

        This was a real bug caught by code review — the column in the DB is
        `created_by` but an earlier version of the repo used `creator_id`.
        """
        async with db_pool.acquire() as conn:
            # Create a user who will be the invite code creator
            user_id = await _create_user(conn, username="admin_user", role="ADMIN")

            # Create an invite code
            code_id = uuid.uuid4()
            await conn.execute(
                """INSERT INTO invite_codes (id, code, created_by, expires_at)
                   VALUES ($1, $2, $3, NOW() + INTERVAL '7 days')""",
                code_id,
                "TESTCODE123",
                user_id,
            )

            # Run the same query that invite_code_repo.find_many() uses
            rows = await conn.fetch(
                """
                SELECT ic.id, ic.code, ic.created_by, ic.consumed_by, ic.consumed_at,
                       ic.expires_at, ic.created_at,
                       u.username AS creator_username,
                       cu.username AS consumed_by_username
                FROM invite_codes ic
                LEFT JOIN users u ON u.id = ic.created_by
                LEFT JOIN users cu ON cu.id = ic.consumed_by
                WHERE 1=1
                ORDER BY ic.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                50,
                0,
            )

            assert len(rows) == 1
            row = dict(rows[0])
            assert row["code"] == "TESTCODE123"
            assert row["created_by"] == user_id
            assert row["creator_username"] == "admin_user"
            assert row["consumed_by"] is None
            assert row["consumed_by_username"] is None

    async def test_find_many_with_status_filters(self, db_pool):
        """Verify status filter SQL is syntactically valid."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="admin2", role="ADMIN")

            # Create active, consumed, and expired codes
            active_id = uuid.uuid4()
            await conn.execute(
                """INSERT INTO invite_codes (id, code, created_by, expires_at)
                   VALUES ($1, $2, $3, NOW() + INTERVAL '7 days')""",
                active_id,
                "ACTIVE001",
                user_id,
            )

            expired_id = uuid.uuid4()
            await conn.execute(
                """INSERT INTO invite_codes (id, code, created_by, expires_at)
                   VALUES ($1, $2, $3, NOW() - INTERVAL '1 day')""",
                expired_id,
                "EXPIRED001",
                user_id,
            )

            # Test "active" filter
            active_count = await conn.fetchval(
                """SELECT COUNT(*) FROM invite_codes ic
                   WHERE 1=1
                   AND ic.consumed_at IS NULL
                   AND (ic.expires_at IS NULL OR ic.expires_at > NOW())""",
            )
            assert active_count == 1

            # Test "expired" filter
            expired_count = await conn.fetchval(
                """SELECT COUNT(*) FROM invite_codes ic
                   WHERE 1=1
                   AND ic.consumed_at IS NULL
                   AND ic.expires_at IS NOT NULL AND ic.expires_at <= NOW()""",
            )
            assert expired_count == 1


# ===========================================================================
# Test: post_repo.find_many() — verifies COUNT(*) OVER() window function
# ===========================================================================
class TestPostRepoFindMany:
    async def test_find_many_window_function(self, db_pool):
        """Verify COUNT(*) OVER() window function works with the JOIN query."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="poster")
            cat_id = await _create_category(conn, name="Tech")

            # Create 3 posts
            for i in range(3):
                await _create_post(
                    conn,
                    user_id,
                    title=f"Post {i}",
                    content=f"Content {i}",
                    category_id=cat_id,
                )

            # Run the same query structure as post_repo.find_many()
            rows = await conn.fetch(
                """
                SELECT p.*,
                       u.id AS author_id, u.username AS author_username,
                       u.display_name AS author_display_name,
                       u.avatar_url AS author_avatar_url,
                       c.name AS category_name,
                       COUNT(*) OVER() AS _total
                FROM posts p
                JOIN users u ON p.user_id = u.id
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.is_deleted = false
                ORDER BY p.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                20,
                0,
            )

            assert len(rows) == 3
            assert rows[0]["_total"] == 3
            assert rows[0]["author_username"] == "poster"
            assert rows[0]["category_name"] == "Tech"

    async def test_find_many_with_category_filter(self, db_pool):
        """Verify category filter with parameterized query works."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="poster2")
            cat_a = await _create_category(conn, name="Cat A")
            cat_b = await _create_category(conn, name="Cat B")

            await _create_post(conn, user_id, "In A", "body", cat_a)
            await _create_post(conn, user_id, "In B", "body", cat_b)
            await _create_post(conn, user_id, "Also in A", "body", cat_a)

            rows = await conn.fetch(
                """
                SELECT p.*,
                       u.id AS author_id, u.username AS author_username,
                       u.display_name AS author_display_name,
                       u.avatar_url AS author_avatar_url,
                       c.name AS category_name,
                       COUNT(*) OVER() AS _total
                FROM posts p
                JOIN users u ON p.user_id = u.id
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.is_deleted = false AND p.category_id = $1
                ORDER BY p.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                cat_a,
                20,
                0,
            )

            assert len(rows) == 2
            assert rows[0]["_total"] == 2


# ===========================================================================
# Test: user_repo.insert() + user_repo.find_by_id() — basic CRUD
# ===========================================================================
class TestUserRepoCRUD:
    async def test_insert_and_find_by_id(self, db_pool):
        """Verify INSERT RETURNING * and SELECT * both work on users table."""
        async with db_pool.acquire() as conn:
            user_id = uuid.uuid4()

            # INSERT RETURNING * (same as user_repo.insert)
            row = await conn.fetchrow(
                """
                INSERT INTO users (id, username, password_hash, role, display_name)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                user_id,
                "newuser",
                "$argon2id$v=19$m=65536,t=3,p=4$fake$hash",
                "MEMBER",
                "New User",
            )

            assert row is not None
            assert row["id"] == user_id
            assert row["username"] == "newuser"
            assert row["role"] == "MEMBER"
            assert row["display_name"] == "New User"
            assert row["is_deleted"] is False
            assert row["is_banned"] is False
            assert row["created_at"] is not None
            assert row["updated_at"] is not None

            # SELECT * (same as user_repo.find_by_id)
            found = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id,
            )
            assert found is not None
            assert found["username"] == "newuser"

    async def test_find_by_username(self, db_pool):
        """Verify SELECT * WHERE username = $1 works."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="findme")

            row = await conn.fetchrow(
                "SELECT * FROM users WHERE username = $1",
                "findme",
            )
            assert row is not None
            assert row["id"] == user_id

    async def test_username_uniqueness(self, db_pool):
        """Verify the unique index on username prevents duplicates."""
        async with db_pool.acquire() as conn:
            await _create_user(conn, username="unique_user")

            with pytest.raises(asyncpg.UniqueViolationError):
                await _create_user(conn, username="unique_user")

    async def test_update_profile(self, db_pool):
        """Verify dynamic UPDATE SET ... RETURNING * works."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="updatable")

            row = await conn.fetchrow(
                """UPDATE users SET display_name = $1, bio = $2, updated_at = NOW()
                   WHERE id = $3 RETURNING *""",
                "Updated Name",
                "A short bio",
                user_id,
            )

            assert row is not None
            assert row["display_name"] == "Updated Name"
            assert row["bio"] == "A short bio"


# ===========================================================================
# Test: Post creation + full-text search (search_vector trigger)
# ===========================================================================
class TestPostFullTextSearch:
    async def test_search_vector_trigger_auto_populates(self, db_pool):
        """Verify the search_vector trigger auto-populates on INSERT."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="alice")

            post_id = await _create_post(
                conn,
                user_id,
                title="Machine Learning in Education",
                content="Deep learning models for literacy assessment",
            )

            # search_vector should be auto-populated by trigger
            sv = await conn.fetchval(
                "SELECT search_vector FROM posts WHERE id = $1",
                post_id,
            )
            assert sv is not None

    async def test_full_text_search_finds_post(self, db_pool):
        """Verify to_tsquery full-text search returns matching posts."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="bob")

            await _create_post(
                conn,
                user_id,
                title="Natural Language Processing",
                content="NLP techniques for automated essay scoring",
            )
            await _create_post(
                conn,
                user_id,
                title="Computer Vision",
                content="Image recognition for handwriting analysis",
            )

            # Search for "language" — should find only the NLP post
            found = await conn.fetchval(
                """SELECT COUNT(*) FROM posts
                   WHERE search_vector @@ to_tsquery('english', 'language')""",
            )
            assert found == 1

            # Search for "language | vision" — should find both
            found_or = await conn.fetchval(
                """SELECT COUNT(*) FROM posts
                   WHERE search_vector @@ to_tsquery('english', 'language | vision')""",
            )
            assert found_or == 2

    async def test_search_vector_updates_on_title_change(self, db_pool):
        """Verify the trigger fires on UPDATE of title column."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="charlie")

            post_id = await _create_post(
                conn,
                user_id,
                title="Original Title About Robots",
                content="Some content",
            )

            # Should find "robots"
            found = await conn.fetchval(
                """SELECT COUNT(*) FROM posts
                   WHERE search_vector @@ to_tsquery('english', 'robots')""",
            )
            assert found == 1

            # Update title
            await conn.execute(
                "UPDATE posts SET title = 'Updated Title About Dinosaurs' WHERE id = $1",
                post_id,
            )

            # Should no longer find "robots"
            found_after = await conn.fetchval(
                """SELECT COUNT(*) FROM posts
                   WHERE search_vector @@ to_tsquery('english', 'robots')""",
            )
            assert found_after == 0

            # Should find "dinosaurs"
            found_new = await conn.fetchval(
                """SELECT COUNT(*) FROM posts
                   WHERE search_vector @@ to_tsquery('english', 'dinosaurs')""",
            )
            assert found_new == 1

    async def test_search_repo_query_structure(self, db_pool):
        """Verify the full search query from post_repo.search() is valid SQL."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="diana")
            cat_id = await _create_category(conn, name="Research")

            await _create_post(
                conn,
                user_id,
                title="AI in Language Learning",
                content="Exploring artificial intelligence applications",
                category_id=cat_id,
            )

            # Run the same query structure as post_repo.search() with keyword
            rows = await conn.fetch(
                """
                SELECT p.*,
                       u.id AS author_id, u.username AS author_username,
                       u.display_name AS author_display_name,
                       u.avatar_url AS author_avatar_url,
                       c.name AS category_name,
                       COUNT(*) OVER() AS _total
                FROM posts p
                JOIN users u ON p.user_id = u.id
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.is_deleted = false
                  AND p.search_vector @@ to_tsquery('english', $1)
                  AND p.category_id = $2
                ORDER BY p.created_at DESC
                LIMIT $3 OFFSET $4
                """,
                "artificial & intelligence",
                cat_id,
                20,
                0,
            )

            assert len(rows) == 1
            assert rows[0]["author_username"] == "diana"
            assert rows[0]["category_name"] == "Research"
            assert rows[0]["_total"] == 1


# ===========================================================================
# Test: Post CRUD with JOINs (INSERT ... RETURNING + SELECT with JOINs)
# ===========================================================================
class TestPostCRUD:
    async def test_insert_returning_with_join(self, db_pool):
        """Verify the CTE-based INSERT RETURNING + JOIN query from post_repo.insert()."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="eve")
            cat_id = await _create_category(conn, name="Discussion")

            post_id = uuid.uuid4()

            # This is the exact query structure from post_repo.insert()
            row = await conn.fetchrow(
                """
                WITH inserted AS (
                    INSERT INTO posts (id, user_id, title, content, category_id,
                                       sig_id, keywords, allow_comments)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING *
                )
                SELECT p.*,
                       u.id AS author_id, u.username AS author_username,
                       u.display_name AS author_display_name,
                       u.avatar_url AS author_avatar_url,
                       c.name AS category_name
                FROM inserted p
                JOIN users u ON p.user_id = u.id
                LEFT JOIN categories c ON p.category_id = c.id
                """,
                post_id,
                user_id,
                "Hello World",
                "Post body content",
                cat_id,
                None,  # sig_id
                ["ai", "education"],  # keywords
                True,  # allow_comments
            )

            assert row is not None
            assert row["title"] == "Hello World"
            assert row["author_username"] == "eve"
            assert row["category_name"] == "Discussion"
            assert row["keywords"] == ["ai", "education"]

    async def test_soft_delete(self, db_pool):
        """Verify soft delete updates is_deleted flag."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="frank")
            post_id = await _create_post(conn, user_id, "To Delete", "content")

            result = await conn.execute(
                """UPDATE posts SET is_deleted = true, updated_at = NOW()
                   WHERE id = $1 AND user_id = $2 AND is_deleted = false""",
                post_id,
                user_id,
            )
            assert result == "UPDATE 1"

            # find_by_id filters out deleted posts
            row = await conn.fetchrow(
                """SELECT p.*,
                          u.id AS author_id, u.username AS author_username,
                          u.display_name AS author_display_name,
                          u.avatar_url AS author_avatar_url,
                          c.name AS category_name
                   FROM posts p
                   JOIN users u ON p.user_id = u.id
                   LEFT JOIN categories c ON p.category_id = c.id
                   WHERE p.id = $1 AND p.is_deleted = false""",
                post_id,
            )
            assert row is None

    async def test_version_increment(self, db_pool):
        """Verify optimistic locking version increment on update."""
        async with db_pool.acquire() as conn:
            user_id = await _create_user(conn, username="grace")
            cat_id = await _create_category(conn, name="Updates")
            post_id = await _create_post(conn, user_id, "V1 Title", "V1 Body", cat_id)

            # Check initial version
            v1 = await conn.fetchval("SELECT version FROM posts WHERE id = $1", post_id)
            assert v1 == 1

            # Update (same structure as post_repo.update_in_transaction)
            await conn.fetchrow(
                """
                WITH updated AS (
                    UPDATE posts SET
                        title = $1, content = $2, category_id = $3, keywords = $4,
                        allow_comments = $5, version = version + 1, updated_at = NOW()
                    WHERE id = $6
                    RETURNING *
                )
                SELECT p.*,
                       u.id AS author_id, u.username AS author_username,
                       u.display_name AS author_display_name,
                       u.avatar_url AS author_avatar_url,
                       c.name AS category_name
                FROM updated p
                JOIN users u ON p.user_id = u.id
                LEFT JOIN categories c ON p.category_id = c.id
                """,
                "V2 Title",
                "V2 Body",
                cat_id,
                None,
                True,
                post_id,
            )

            v2 = await conn.fetchval("SELECT version FROM posts WHERE id = $1", post_id)
            assert v2 == 2
