"""albums — activity album tables

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-15

"""

from alembic import op

revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # albums
    op.execute("""
        CREATE TABLE albums (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(200) NOT NULL,
            description TEXT,
            cover_photo_url TEXT,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            is_archived BOOLEAN NOT NULL DEFAULT false,
            is_deleted BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_albums_created_at ON albums(created_at DESC)")
    op.execute(
        "CREATE INDEX ix_albums_not_deleted ON albums(created_at DESC) "
        "WHERE is_deleted = false"
    )

    # album_members
    op.execute("""
        CREATE TABLE album_members (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            album_id UUID NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(10) NOT NULL DEFAULT 'MEMBER'
                CHECK (role IN ('ADMIN', 'MEMBER')),
            status VARCHAR(10) NOT NULL DEFAULT 'ACCEPTED'
                CHECK (status IN ('PENDING', 'ACCEPTED', 'REJECTED')),
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_album_member UNIQUE (album_id, user_id)
        )
    """)
    op.execute("CREATE INDEX ix_album_members_album ON album_members(album_id)")
    op.execute("CREATE INDEX ix_album_members_user ON album_members(user_id)")

    # album_photos
    op.execute("""
        CREATE TABLE album_photos (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            album_id UUID NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
            uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
            storage_key TEXT NOT NULL,
            thumbnail_key TEXT,
            original_filename VARCHAR(255),
            file_size_bytes BIGINT NOT NULL DEFAULT 0,
            content_type VARCHAR(50),
            description TEXT,
            width INTEGER,
            height INTEGER,
            is_zip BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX ix_album_photos_album "
        "ON album_photos(album_id, created_at DESC)"
    )
    op.execute("CREATE INDEX ix_album_photos_uploader ON album_photos(uploaded_by)")

    # album_comments
    op.execute("""
        CREATE TABLE album_comments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            album_id UUID NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
            photo_id UUID REFERENCES album_photos(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            parent_id UUID REFERENCES album_comments(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX ix_album_comments_album "
        "ON album_comments(album_id, created_at)"
    )
    op.execute("CREATE INDEX ix_album_comments_photo ON album_comments(photo_id)")
    op.execute("CREATE INDEX ix_album_comments_parent ON album_comments(parent_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS album_comments CASCADE")
    op.execute("DROP TABLE IF EXISTS album_photos CASCADE")
    op.execute("DROP TABLE IF EXISTS album_members CASCADE")
    op.execute("DROP TABLE IF EXISTS albums CASCADE")
