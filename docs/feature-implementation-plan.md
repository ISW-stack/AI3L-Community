# AI3L Community — 7 Features Implementation Plan

> Generated: 2026-03-15 | Status: Planning | Audit: Complete

## Table of Contents

- [Executive Summary](#executive-summary)
- [Implementation Order & Dependencies](#implementation-order--dependencies)
- [Feature 1: Forms Top-Level](#feature-1-forms-top-level)
- [Feature 2: Activity Albums](#feature-2-activity-albums)
- [Feature 3: Post Co-Authors](#feature-3-post-co-authors)
- [Feature 4: Friends / Blacklist / Follow](#feature-4-friends--blacklist--follow)
- [Feature 5: View Counts & Citations](#feature-5-view-counts--citations)
- [Feature 6: Friend Recommendations](#feature-6-friend-recommendations)
- [Feature 7: Q&A Section](#feature-7-qa-section)
- [Cross-Feature Dependencies](#cross-feature-dependencies)
- [Complete File Inventory](#complete-file-inventory)
- [Risk Assessment](#risk-assessment)

---

## Executive Summary

| # | Feature | Resource Impact | Complexity | New Tables | New Files | Modified Files |
|---|---------|----------------|------------|------------|-----------|----------------|
| 1 | Forms Top-Level | Low | Low | 0 | 3 | ~24 |
| 2 | Activity Albums | Medium-High | High | 4 | 19 | 10 |
| 3 | Post Co-Authors | Low-Medium | Medium | 1 | 14 | 18 |
| 4 | Friends/Blacklist/Follow | **High** | **High** | 3 | 6 | ~20 |
| 5 | View Counts & Citations | Medium | Medium | 2 | 7 | ~15 |
| 6 | Friend Recommendations | Medium | Medium | 2 | 10 | ~14 |
| 7 | Q&A Section | Medium | Medium | 1 | 21 | ~22 |

**Total estimated new DB tables: 13 | New files: ~80 | Modified files: ~100+**

---

## Implementation Order & Dependencies

```
Phase 1 ──► Feature 1 (Forms Top-Level)         ← simplest, no dependencies
Phase 2 ──► Feature 3 (Post Co-Authors)          ← low complexity
Phase 3 ──► Feature 7 (Q&A Section)              ← medium, extends existing posts
Phase 4 ──► Feature 5 (View Counts & Citations)  ← medium, Redis dedup
Phase 5 ──► Feature 2 (Activity Albums)          ← new module, high complexity
Phase 6 ──► Feature 4 (Friends/Blacklist/Follow) ← highest blast radius
Phase 7 ──► Feature 6 (Friend Recommendations)   ← depends on Feature 4
```

**Critical dependency:** Feature 6 requires Feature 4 to be complete (friendships table, blocked users table).

---

## Feature 1: Forms Top-Level

### 1.1 Overview

Extract forms from SIG-only context to become an independent top-level feature. Forms can exist standalone or within a SIG. Sharing forms in posts renders as a link card (already supported by existing `FormShareCard` component).

### 1.2 Database Changes

**Migration:** `make_form_sig_id_nullable.py`

```sql
-- Upgrade
ALTER TABLE forms ALTER COLUMN sig_id DROP NOT NULL;
CREATE INDEX ix_forms_standalone ON forms (created_by, created_at DESC)
    WHERE sig_id IS NULL AND is_deleted = false;

-- Downgrade
DELETE FROM form_responses WHERE form_id IN (SELECT id FROM forms WHERE sig_id IS NULL);
DELETE FROM forms WHERE sig_id IS NULL;
ALTER TABLE forms ALTER COLUMN sig_id SET NOT NULL;
DROP INDEX IF EXISTS ix_forms_standalone;
```

### 1.3 Backend Changes

#### Constants (`core/constants.py`)
```python
MAX_ACTIVE_STANDALONE_FORMS_PER_USER = 10
```

#### Schema (`schemas/form.py`)
```python
# Change sig_id from required to optional
sig_id: str | None  # was: sig_id: str
```

#### Repository (`repositories/form_repo.py`)

New functions:
- `find_standalone(page, page_size)` — query standalone forms (`sig_id IS NULL`)
- `count_active_by_user(user_id)` — for standalone form limit enforcement

Modified:
- `insert()` — `sig_id` parameter becomes `uuid.UUID | None`

#### Converter (`converters/form_converter.py`)
```python
# Fix str(None) crash
"sig_id": str(row["sig_id"]) if row.get("sig_id") else None,
```

#### Service (`services/form.py`)

Modified:
- `create_form()` — when `sig_id is None`: skip SIG limit check, enforce per-user standalone limit, force `allow_non_members = True`
- `submit_response()` — skip SIG membership check when `sig_id IS NULL`

New:
- `list_standalone_forms(page, page_size)`

#### Dependencies (`core/deps.py`)

New helper for public access to standalone forms:
```python
async def get_optional_current_user(request, credentials) -> dict | None:
    try:
        return await get_current_user(request, credentials)
    except AppError:
        return None
```

#### Endpoints (`api/v1/endpoints/forms.py`)

New:
- `POST /forms` — create standalone form (MEMBER+ auth)
- `GET /forms` — list standalone forms (no auth required)

Modified:
- `GET /forms/{form_id}` — use `get_optional_current_user` for standalone form public access
- `_is_sig_admin()` — handle `sig_id=None` (return `False` for non-admins)
- All `uuid.UUID(form["sig_id"])` calls — guard with `if form["sig_id"]`

**Route ordering:** `POST /forms` and `GET /forms` declared BEFORE `GET /forms/{form_id}`.

### 1.4 Frontend Changes

#### Types (`types/form.ts`)
```typescript
sig_id: string | null  // was: string
```

#### API (`api/forms.ts`)

New:
- `createStandaloneForm(payload)` — `POST /forms`
- `listStandaloneForms(page, pageSize)` — `GET /forms`

#### Router (`router/index.ts`)

New routes (before `/forms/:formId`):
```typescript
{ path: '/forms', name: 'forms', component: FormsDirectoryView }
{ path: '/forms/new', name: 'standalone-form-create', component: FormBuilderView, meta: { requiresAuth: true, requiresMember: true } }
```

Remove `requiresAuth` from `/forms/:formId` (standalone forms are public).

#### New View: `views/forms/FormsDirectoryView.vue`
- Paginated grid of standalone forms
- "Create Form" button (visible to authenticated non-guest users)
- Each card: title, description, status, response count, deadline, creator name

#### Modified Views

**FormBuilderView.vue:**
- Breadcrumb: `Home > Forms > Create` (when no `sigId`)
- Hide `allowNonMembers` checkbox for standalone forms

**FormView.vue:**
- Breadcrumb: `Home > Forms > [Title]` (when `sig_id` is null)
- "Back to Forms" button instead of "Back to SIG"

#### Composables

**useFormBuilder.ts:**
- `isStandalone` computed: `!sigId()`
- Standalone save calls `createStandaloneForm()`, redirects to `/forms/{id}`

**useFormSubmit.ts:**
- Guard `getSig()` call: only when `sig_id` is not null
- `goBackToSig()` → navigate to `/forms` for standalone

**useFormDraft.ts:**
- `'form-draft-unknown'` → `'form-draft-standalone'`

#### Navigation (`AppNavbar.vue`)
- Add "Forms" link after SIGs

### 1.5 Link Card (No Changes Needed)

The existing `FormShareCard` + `usePostDetail.ts` content segment parsing already detects `/forms/{uuid}` URLs and renders them as link cards. **No TipTap extension changes required.**

### 1.6 Tests

**Backend (~14 new test cases):**
- Standalone form CRUD, guest access, limit enforcement, SIG check skip on submit

**Frontend (~3 new test files):**
- `FormsDirectoryView.spec.ts`, updated `FormBuilderView.spec.ts`, `FormView.spec.ts`

---

## Feature 2: Activity Albums

### 2.1 Overview

New top-level feature for event photo galleries. Admin-created, member participation, shared upload quota, auto-thumbnails, ZIP downloads.

### 2.2 Database Changes

**Migration:** `add_album_tables.py`

**Table: `albums`**
```sql
CREATE TABLE albums (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    cover_photo_url TEXT,
    created_by UUID NOT NULL REFERENCES users(id),
    is_archived BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_albums_created_at ON albums(created_at DESC);
```

**Table: `album_members`**
```sql
CREATE TABLE album_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    album_id UUID NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL DEFAULT 'MEMBER' CHECK (role IN ('ADMIN', 'MEMBER')),
    status VARCHAR(10) NOT NULL DEFAULT 'ACCEPTED' CHECK (status IN ('PENDING', 'ACCEPTED', 'REJECTED')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_album_member UNIQUE (album_id, user_id)
);
CREATE INDEX ix_album_members_album ON album_members(album_id);
CREATE INDEX ix_album_members_user ON album_members(user_id);
```

**Table: `album_photos`**
```sql
CREATE TABLE album_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    album_id UUID NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
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
);
CREATE INDEX ix_album_photos_album ON album_photos(album_id, created_at DESC);
CREATE INDEX ix_album_photos_uploader ON album_photos(uploaded_by);
```

**Table: `album_comments`**
```sql
CREATE TABLE album_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    album_id UUID NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    photo_id UUID REFERENCES album_photos(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    parent_id UUID REFERENCES album_comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_album_comments_album ON album_comments(album_id, created_at);
CREATE INDEX ix_album_comments_photo ON album_comments(photo_id);
CREATE INDEX ix_album_comments_parent ON album_comments(parent_id);
```

### 2.3 Constants (`core/constants.py`)

```python
ALBUM_MAX_PHOTO_SIZE_BYTES = 10 * 1024 * 1024      # 10 MB
ALBUM_MAX_ZIP_SIZE_BYTES = 100 * 1024 * 1024        # 100 MB
ALBUM_THUMBNAIL_SIZE = (400, 400)                     # pixels
ALBUM_THUMBNAIL_QUALITY = 85
ALBUM_MAX_PHOTOS = 50                                 # per album
ALBUM_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALBUM_ALLOWED_ZIP_TYPES = {"application/zip", "application/x-zip-compressed"}
RATE_LIMIT_ALBUM_UPLOAD = ("ALBUM_UPLOAD", 10, 60)   # 10 uploads/min
```

### 2.4 Storage Keys (`core/storage.py`)

```python
# New key generators
def album_photo_key(album_id, filename_uuid, ext): return f"albums/{album_id}/photos/{filename_uuid}.{ext}"
def album_thumbnail_key(album_id, filename_uuid): return f"albums/{album_id}/thumbs/{filename_uuid}.webp"
def album_zip_key(album_id, filename_uuid, ext): return f"albums/{album_id}/files/{filename_uuid}.{ext}"
```

### 2.5 Thumbnail Generation (`tasks/thumbnail.py`)

Celery task using Pillow (already a dependency):

```python
@celery.task(name="generate_thumbnail", bind=True, max_retries=2)
def generate_thumbnail_task(self, storage_key: str, thumbnail_key: str):
    """Download image from MinIO, resize to 400x400 fit, save as WebP."""
    # 1. Download original from MinIO
    # 2. Pillow: Image.open() → thumbnail(ALBUM_THUMBNAIL_SIZE) → save as WebP
    # 3. Upload thumbnail to MinIO
    # 4. Update album_photos.thumbnail_key in DB
```

### 2.6 Backend Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/albums` | ADMIN+ | Create album |
| `GET` | `/albums` | AUTH | List all albums (paginated) |
| `GET` | `/albums/{id}` | AUTH | Get album detail |
| `PUT` | `/albums/{id}` | ADMIN/creator | Update album title/description |
| `DELETE` | `/albums/{id}` | ADMIN/creator | Soft-delete album |
| `POST` | `/albums/{id}/members` | ADMIN/creator | Add member to album |
| `POST` | `/albums/{id}/join` | MEMBER+ | Request to join album |
| `PUT` | `/albums/{id}/members/{mid}/approve` | ADMIN/creator | Approve join request |
| `DELETE` | `/albums/{id}/members/{uid}` | ADMIN/creator/self | Remove member |
| `GET` | `/albums/{id}/members` | AUTH | List album members |
| `POST` | `/albums/{id}/photos` | Album member | Upload photo (consumes quota) |
| `POST` | `/albums/{id}/files` | Album member | Upload ZIP (consumes quota) |
| `GET` | `/albums/{id}/photos` | AUTH | List photos (paginated) |
| `GET` | `/albums/{id}/photos/{pid}` | AUTH | Get photo detail + presigned URL |
| `PUT` | `/albums/{id}/photos/{pid}` | Uploader/ADMIN | Update photo description |
| `DELETE` | `/albums/{id}/photos/{pid}` | Uploader/ADMIN | Delete photo (refund quota) |
| `POST` | `/albums/{id}/comments` | Album member | Add comment |
| `GET` | `/albums/{id}/comments` | AUTH | List comments (threaded) |
| `DELETE` | `/albums/{id}/comments/{cid}` | Author/ADMIN | Delete comment |

**Delete permission rule:** Uploader can self-delete. ADMIN can delete any except other ADMIN's uploads.

**Upload flow:**
1. Validate file type + size
2. Acquire per-user upload lock (Redis `SETNX`)
3. Check storage quota: `get_storage_used(user_id) + file_size <= MAX_USER_STORAGE_BYTES`
4. Upload to MinIO
5. `increment_storage_used(user_id, file_size)`
6. Insert `album_photos` row
7. If image (not ZIP): dispatch `generate_thumbnail` Celery task

### 2.7 Frontend Structure

**New views:**
- `views/albums/AlbumsDirectoryView.vue` — album listing grid
- `views/albums/AlbumLayout.vue` — parent layout (provide/inject pattern, like SigLayout)
- `views/albums/AlbumPhotosView.vue` — photo grid child view
- `views/albums/AlbumMembersView.vue` — members child view
- `views/albums/AlbumCommentsView.vue` — comments child view

**New components:**
- `components/albums/AlbumCard.vue` — album card for directory
- `components/albums/PhotoGrid.vue` — thumbnail grid with lightbox trigger
- `components/albums/PhotoUploadModal.vue` — upload modal with quota display
- `components/albums/PhotoLightbox.vue` — full-size image viewer

**Router:**
```typescript
{ path: '/albums', name: 'albums', component: AlbumsDirectoryView, meta: { requiresAuth: true } }
{ path: '/albums/:id', component: AlbumLayout, meta: { requiresAuth: true }, children: [
    { path: '', redirect: 'photos' },
    { path: 'photos', name: 'album-photos', component: AlbumPhotosView },
    { path: 'members', name: 'album-members', component: AlbumMembersView },
    { path: 'comments', name: 'album-comments', component: AlbumCommentsView },
]}
```

---

## Feature 3: Post Co-Authors

### 3.1 Overview

Junction table approach for co-authorship. Internal members require invitation acceptance. External co-authors have name + affiliation + ORCID. Accepted internal co-authors can edit the post (via existing optimistic locking).

### 3.2 Database Changes

**Migration:** `add_post_co_authors_table.py`

```sql
CREATE TABLE post_co_authors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    display_name VARCHAR(100) NOT NULL,
    affiliation VARCHAR(200),
    orcid VARCHAR(30),
    is_external BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(10) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'ACCEPTED', 'REJECTED')),
    invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    invited_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_post_co_author UNIQUE (post_id, user_id),
    CONSTRAINT chk_internal_user CHECK (
        (is_external = TRUE) OR (user_id IS NOT NULL)
    )
);
CREATE INDEX ix_post_co_authors_post_id ON post_co_authors(post_id);
CREATE INDEX ix_post_co_authors_user_id ON post_co_authors(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX ix_post_co_authors_status ON post_co_authors(post_id, status);
```

**Design notes:**
- `ON DELETE SET NULL` on `user_id`: deleted member's attribution survives as snapshot `display_name`
- External co-authors: always `status = 'ACCEPTED'` immediately
- Max 10 co-authors per post (`MAX_CO_AUTHORS_PER_POST = 10` in constants)

### 3.3 Backend Endpoints

**Post-scoped co-author management:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/posts/{post_id}/co-authors/invite` | MEMBER+ | Invite internal co-author |
| `POST` | `/posts/{post_id}/co-authors/external` | MEMBER+ | Add external co-author |
| `GET` | `/posts/{post_id}/co-authors` | Any auth | List co-authors |
| `DELETE` | `/posts/{post_id}/co-authors/{id}` | Owner/ADMIN | Remove co-author |

**User invitation management:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/users/me/co-author-invitations` | Any auth | List pending invitations |
| `PUT` | `/users/me/co-author-invitations/{id}/accept` | Any auth | Accept |
| `PUT` | `/users/me/co-author-invitations/{id}/reject` | Any auth | Reject |
| `GET` | `/users/me/co-authored-posts` | Any auth | List co-authored posts |

**User search for invitation UI:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/users/search?q=...&limit=5` | MEMBER+ | Search members by name/username |

**Route ordering:** `/users/search` and `/users/me/co-author-invitations/*` BEFORE `/{user_id}` in users router.

### 3.4 Permission Model

**Co-author editing:**
```python
# Modified update_post permission check
is_owner = str(current["user_id"]) == user_id
is_co_author = await co_author_repo.is_accepted_co_author(post_id, uuid.UUID(user_id))
if not is_owner and not is_admin and not is_co_author:
    raise PermissionError(...)
```

Optimistic locking (`version` field) handles concurrent edits between author and co-authors — same 409 conflict mechanism.

### 3.5 Post Response Enrichment

Co-authors are attached at the **service layer** (not via JOIN to avoid cartesian product):

```sql
-- Batch query for post list (single query for all posts)
SELECT pca.*, u.display_name AS user_display_name, u.avatar_url AS user_avatar_url
FROM post_co_authors pca
LEFT JOIN users u ON pca.user_id = u.id
WHERE pca.post_id = ANY($1::uuid[]) AND pca.status = 'ACCEPTED'
ORDER BY pca.invited_at ASC
```

### 3.6 Notification Integration

Two new events:
- `co_author.invited` → notify target user
- `co_author.responded` → notify post owner (accepted/declined)

New action types: `CO_AUTHOR_INVITE`, `CO_AUTHOR_RESPONSE`

### 3.7 Frontend Components

**New:**
- `components/post/CoAuthorManager.vue` — manage co-authors in post detail (owner only)
- `components/post/CoAuthorBadges.vue` — compact inline display for post list cards

**Modified:**
- `PostCard.vue` — show co-author badges after author name
- `PostDetailView.vue` — show co-authors + CoAuthorManager
- `usePostDetail.ts` — add `isCoAuthor`, update `canModify`
- `ProfileView.vue` — add "Invitations" tab
- `UserProfileView.vue` — add "Co-Authored Posts" tab

---

## Feature 4: Friends / Blacklist / Follow

### 4.1 Overview

Full social relationship system. Friends (bilateral, request-based), Follow (unilateral), Blacklist (bilateral, max 5). Blacklist filters ALL content queries via Redis-cached sets.

### 4.2 Database Changes

**Migration:** `add_social_relationships.py`

```sql
-- Friendships (bilateral, request/accept flow)
CREATE TABLE friendships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id UUID NOT NULL REFERENCES users(id),
    addressee_id UUID NOT NULL REFERENCES users(id),
    status VARCHAR(10) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACCEPTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_friendship UNIQUE (requester_id, addressee_id),
    CONSTRAINT ck_friendship_self CHECK (requester_id != addressee_id)
);

-- Follows (unilateral)
CREATE TABLE follows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_id UUID NOT NULL REFERENCES users(id),
    following_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_follow UNIQUE (follower_id, following_id),
    CONSTRAINT ck_follow_self CHECK (follower_id != following_id)
);

-- Blocks (bilateral blocking, max 5 per user)
CREATE TABLE blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blocker_id UUID NOT NULL REFERENCES users(id),
    blocked_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_block UNIQUE (blocker_id, blocked_id),
    CONSTRAINT ck_block_self CHECK (blocker_id != blocked_id)
);
```

### 4.3 Redis Blacklist Cache

**Key pattern:** `block:set:{user_id}` — Redis SET containing all user IDs in bilateral block relationship.

**Warmup on startup:**
```python
async def warmup_block_cache():
    rows = await conn.fetch("SELECT blocker_id, blocked_id FROM blocks")
    pipe = redis.pipeline()
    for row in rows:
        pipe.sadd(f"block:set:{blocker}", blocked)
        pipe.sadd(f"block:set:{blocked}", blocker)
    await pipe.execute()
```

**Cache invalidation:** on block/unblock, update both parties' sets immediately.

**Memory estimate:** Max 5 blocks/user × 1000 users = ~380 KB. Negligible.

### 4.4 Backend Endpoints

**Friends:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/social/friends/request` | MEMBER+ | Send friend request |
| `PUT` | `/social/friends/{id}/accept` | MEMBER+ | Accept request (auto-follows both) |
| `PUT` | `/social/friends/{id}/reject` | MEMBER+ | Reject request |
| `DELETE` | `/social/friends/{user_id}` | MEMBER+ | Unfriend (does NOT auto-unfollow) |
| `GET` | `/social/friends` | MEMBER+ | List accepted friends |
| `GET` | `/social/friends/requests` | MEMBER+ | List pending requests (in/out) |

**Follow:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/social/follow/{user_id}` | MEMBER+ | Follow user |
| `DELETE` | `/social/follow/{user_id}` | MEMBER+ | Unfollow user |
| `GET` | `/social/followers` | MEMBER+ | List my followers |
| `GET` | `/social/following` | MEMBER+ | List who I follow |

**Block:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/social/block/{user_id}` | MEMBER+ | Block user (max 5, auto-unfriends, auto-unfollows both) |
| `DELETE` | `/social/block/{user_id}` | MEMBER+ | Unblock user |
| `GET` | `/social/blocks` | MEMBER+ | List blocked users |

**Relationship status:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/social/status/{user_id}` | MEMBER+ | Get full relationship status |

**Response schema:**
```python
class RelationshipStatusResponse(BaseModel):
    is_friend: bool
    is_following: bool
    is_followed_by: bool
    is_blocked: bool
    is_blocked_by: bool
    pending_request: str | None  # null | "sent" | "received"
    friendship_id: str | None
```

### 4.5 Content Filtering Strategy

**Approach:** Service-layer filtering with SQL fragment injection.

**Helper (`core/blacklist.py`):**
```python
async def get_blocked_user_ids(user_id: str) -> set[str]:
    """Get bilateral block set from Redis. Falls back to DB on miss."""

def build_block_exclusion_clause(blocked_ids, user_column, param_idx):
    """Return SQL fragment: AND {user_column} != ALL($N::uuid[])"""
```

**Pattern A — Post-fetch check (single-item fetches):**
After fetching, check if author is in viewer's block set. If yes, return None (treated as "not found").

**Pattern B — Query parameter injection (list/search operations):**
Add `exclude_user_ids: list[uuid.UUID] | None = None` parameter to repo functions.

### 4.6 Every File Requiring Blacklist Filtering

**Repositories:**
| File | Function(s) | Column to filter |
|------|-------------|-----------------|
| `post_repo.py` | `find_many()`, `search()`, `find_trending()` | `p.user_id` |
| `comment_repo.py` | `find_many()` | `cm.user_id` |
| `notification_repo.py` | `find_many()` | `n.trigger_user_id` |
| `form_repo.py` | `find_responses()` | response `user_id` |

**Services:**
| File | Change |
|------|--------|
| `services/post.py` | Call `get_blocked_user_ids()`, pass to repo |
| `services/comment.py` | Pass blocked IDs; block check on `create_comment` |
| `services/notification.py` | Filter notifications; suppress blocked-user notifications |
| `services/form.py` | Block check on `submit_response()`, filter `list_form_responses()` |

**Endpoints:**
| File | Change |
|------|--------|
| `endpoints/posts.py` | Pass viewer context to service |
| `endpoints/comments.py` | Pass viewer context |
| `endpoints/notifications.py` | Pass viewer context |
| `endpoints/forms.py` | Block check on submit, filter responses |
| `endpoints/users.py` | Return 404 for blocked profile |
| `endpoints/sigs.py` | Pass viewer ID for SIG posts filtering |

**Event handlers:**
| File | Change |
|------|--------|
| `event_handlers.py` | Block check before ALL notifications (comment, SIG post, follow) |

### 4.7 Block Cascade Logic

When A blocks B:
1. Delete friendship record (both directions)
2. Delete both follow records (A→B and B→A)
3. Insert block record
4. Update Redis block sets for both A and B
5. All in a single transaction

### 4.8 Edge Cases

- **Blocking a friend:** auto-unfriend (cascade above)
- **Blocking someone in same SIG:** SIG membership unaffected, but posts/comments filtered
- **Admin bypass:** Admin panel queries skip blacklist filtering
- **Max 5 enforcement:** `SELECT COUNT(*) FROM blocks WHERE blocker_id = $1` before INSERT
- **Duplicate friend request:** if B already sent to A, auto-accept instead of duplicate
- **Account deletion (GDPR):** cleanup all friendship/follow/block records + Redis cache

### 4.9 Follow Notifications

New event: `post.created` → notify all followers (with block check + SIG dedup).

New notification action types: `FOLLOW_NEW_POST`, `FRIEND_REQUEST`, `FRIEND_ACCEPTED`

### 4.10 Frontend

**New files:**
- `api/social.ts` — all social API functions
- `types/social.ts` — relationship types
- `composables/useSocialStatus.ts` — fetch/cache relationship status
- `components/social/SocialActions.vue` — Follow/Friend/Block buttons
- `components/social/FriendRequestCard.vue`
- `views/FriendsView.vue`, `views/FollowersView.vue`, `views/BlockedUsersView.vue`

**Modified:**
- `UserProfileView.vue` — add SocialActions component, hide for blocked
- `ProfileView.vue` — links to Friends/Following/Blocked settings
- `router/index.ts` — `/friends`, `/following`, `/blocked-users`
- `AppNavbar.vue` — Friends link

---

## Feature 5: View Counts & Citations

### 5.1 Overview

Profile view tracking (unique + total, 24h dedup). Post view dedup upgraded to 24h. In-site citations with pure text format. Citation notifications.

### 5.2 Database Changes

**Migration:** `add_citations_and_profile_views.py`

**Table: `profile_views`**
```sql
CREATE TABLE profile_views (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    viewer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    view_count INTEGER NOT NULL DEFAULT 1,
    first_viewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_viewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_profile_views_unique ON profile_views (profile_id, viewer_id);
CREATE INDEX idx_profile_views_profile_id ON profile_views (profile_id);
```

**Design:** One row per (profile, viewer) pair. `view_count` tracks repeat visits. Unique visitors = `COUNT(*)`. Total views = `SUM(view_count)`.

**Denormalized counters on `users`:**
```sql
ALTER TABLE users ADD COLUMN profile_view_count_unique INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN profile_view_count_total INTEGER NOT NULL DEFAULT 0;
```

**Table: `post_citations`**
```sql
CREATE TABLE post_citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citing_post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    cited_post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    is_self_citation BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_post_citations_unique ON post_citations (citing_post_id, cited_post_id);
CREATE INDEX idx_post_citations_cited ON post_citations (cited_post_id);
```

**Denormalized counter on `posts`:**
```sql
ALTER TABLE posts ADD COLUMN citation_count INTEGER NOT NULL DEFAULT 0;
```

### 5.3 Post View Count Upgrade

Change Redis dedup TTL from 300 (5 min) to 86400 (24 hours) in `services/post.py`:
```python
# Key: viewed:{post_id}:{viewer_id}, TTL: 86400
await redis.set(key, "1", ex=86400, nx=True)
```

### 5.4 Profile View Tracking

```python
async def record_profile_view(profile_id: str, viewer_id: str):
    if profile_id == viewer_id: return  # skip self-views
    key = f"profile_viewed:{profile_id}:{viewer_id}"
    is_new = await redis.set(key, "1", ex=86400, nx=True)
    if not is_new: return  # already viewed in 24h

    # Upsert profile_views row
    is_new_viewer = await profile_view_repo.upsert_view(profile_id, viewer_id)
    await profile_view_repo.increment_total(profile_id)
    if is_new_viewer:
        await profile_view_repo.increment_unique(profile_id)
```

**Celery Beat reconciliation (every 6 hours):** recompute denormalized counters from `profile_views` table.

### 5.5 Citation System

#### Citation Format in HTML

```html
<a href="/forum/{cited_post_id}" data-citation="true" class="citation">[Cite: Post Title]</a>
```

**nh3 sanitizer update:** Add `data-citation` and `class` to allowed attrs for `<a>`.

#### Citation Sync on Post Save

`sync_post_citations(post_id, content, author_id, conn)`:
1. Parse cited post IDs from HTML using regex
2. Diff against existing citations
3. Delete removed citations, insert new ones
4. Set `is_self_citation` flag
5. Recalculate `citation_count` for all affected posts
6. Emit `post.cited` event for new citations (no notification for self-citations)

#### Citation Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/posts/{id}/citations` | AUTH | Posts that cite this post ("Cited by N") |
| `GET` | `/posts/{id}/citing` | AUTH | Posts that this post cites ("References") |
| `POST` | `/posts/search-for-citation` | MEMBER+ | Search posts for citation dialog |

**Route ordering:** `/posts/search-for-citation` BEFORE `/{post_id}`.

### 5.6 Frontend

**TipTap toolbar:** New "Cite" button → opens `CitationSearchDialog.vue` → search posts → insert citation link at cursor.

**PostDetailView.vue:**
- "Cited N times" expandable section (links to citing posts)
- "References (N)" section (posts this post cites)
- Self-citations marked with "(self)" badge

**PostCard.vue:** Show `citation_count` icon in action bar.

**UserProfileView.vue:** Show `profile_view_count_unique` and `profile_view_count_total`.

**Schema updates:**
- `PostResponse.citation_count: int = 0`
- `PublicUserResponse.profile_view_count_unique: int = 0`
- `PublicUserResponse.profile_view_count_total: int = 0`

---

## Feature 6: Friend Recommendations

### 6.1 Overview

Daily Celery Beat task computes multi-signal friend recommendations. Stored in DB, displayed on homepage sidebar + profile page. Max 10 per user. Dismissible. Only activates when > 10 users.

**Prerequisite:** Feature 4 (Friends system) must be implemented first.

### 6.2 Database Changes

**Migration:** `add_friend_recommendations.py`

```sql
CREATE TABLE friend_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recommended_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    score REAL NOT NULL DEFAULT 0.0,
    reasons JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_friend_rec_user_pair UNIQUE (user_id, recommended_user_id),
    CONSTRAINT ck_friend_rec_no_self CHECK (user_id <> recommended_user_id)
);
CREATE INDEX ix_friend_rec_user_score ON friend_recommendations (user_id, score DESC);

CREATE TABLE dismissed_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dismissed_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dismissed_pair UNIQUE (user_id, dismissed_user_id)
);
CREATE INDEX ix_dismissed_user ON dismissed_recommendations (user_id);
```

### 6.3 Algorithm Design

**Scoring formula:**
```
total_score = (S1 × 0.30) + (S2 × 0.25) + (S3 × 0.25) + (S4 × 0.10) + (S5 × 0.10)
```

| Signal | Weight | Description | Normalization |
|--------|--------|-------------|---------------|
| S1: Common SIG membership | 0.30 | Shared SIG count | `min(count / 3.0, 1.0)` |
| S2: Mutual friends (FoF) | 0.25 | Shared friend count | `min(count / 5.0, 1.0)` |
| S3: Similar keywords/categories | 0.25 | Jaccard similarity of post keywords | 0.0 – 1.0 |
| S4: Same affiliation | 0.10 | Binary match on `LOWER(TRIM(affiliation))` | 0.0 or 1.0 |
| S5: Activity recency | 0.10 | `exp(-0.05 × days_since_last_activity)` | 0.0 – 1.0 |

**Exclusions:** self, already friends, blocked, dismissed, deleted/banned, guests.

**Selection:** Top 10 per user, minimum score threshold 0.05.

**Cold start:** Users with no activity get no recommendations (acceptable). System with ≤ 10 users: task exits immediately.

### 6.4 Celery Beat Task

```python
# In celery_app.py beat_schedule:
"compute-friend-recommendations": {
    "task": "compute_friend_recommendations",
    "schedule": 86400.0,  # daily
    "options": {"soft_time_limit": 600, "time_limit": 900},
}
```

**SQL strategy:** Single large query with CTEs computing all signals via set-based joins. For ~1000 users (~500K pairs): runs in seconds.

**Process:**
1. Check user count > 10
2. Compute all signal scores via SQL CTEs
3. `TRUNCATE friend_recommendations`
4. Batch INSERT top-10 per user with reasons JSONB

### 6.5 Backend Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/recommendations/friends` | MEMBER+ | Get precomputed recommendations |
| `POST` | `/recommendations/friends/dismiss` | MEMBER+ | Dismiss (won't reappear) |

### 6.6 Frontend

**New component: `FriendRecommendations.vue`**
- Self-contained sidebar widget
- Fetches data on mount
- Shows up to 10 recommendations with avatar, name, reason summary
- Dismiss button (optimistic UI)
- Only renders for authenticated non-guest users

**Integration:**
- `HomeView.vue` — right sidebar
- `UserProfileView.vue` — own profile only

**Reasons display example:**
```
"Both in Machine Learning SIG"
"3 mutual friends"
"Same affiliation: MIT"
```

---

## Feature 7: Q&A Section

### 7.1 Overview

Extends existing `posts` and `comments` tables with type discrimination. Questions are posts with `type='question'`. Answers are comments with voting and best-answer marking. Auto-assignment invites experts based on keyword matching.

### 7.2 Database Changes

**Migration:** `add_qa_feature.py`

**New columns on `posts`:**
```sql
ALTER TABLE posts ADD COLUMN type VARCHAR(20) NOT NULL DEFAULT 'post';
ALTER TABLE posts ADD COLUMN best_answer_id UUID REFERENCES comments(id) ON DELETE SET NULL;
ALTER TABLE posts ADD COLUMN answer_count INTEGER NOT NULL DEFAULT 0;
CREATE INDEX ix_posts_type ON posts(type);
CREATE INDEX ix_posts_type_created_at ON posts(type, created_at DESC) WHERE is_deleted = false;
```

**New columns on `comments`:**
```sql
ALTER TABLE comments ADD COLUMN is_best_answer BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE comments ADD COLUMN vote_score INTEGER NOT NULL DEFAULT 0;
CREATE INDEX ix_comments_post_id_vote_score ON comments(post_id, vote_score DESC) WHERE is_deleted = false;
```

**New table: `comment_votes`**
```sql
CREATE TABLE comment_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vote SMALLINT NOT NULL CHECK (vote IN (-1, 1)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_comment_votes_comment_user UNIQUE (comment_id, user_id)
);
```

### 7.3 Backend Endpoints

**Q&A-specific endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/qa/{post_id}/best-answer` | MEMBER+ | Mark best answer (question author only) |
| `DELETE` | `/qa/{post_id}/best-answer` | MEMBER+ | Unmark best answer |
| `POST` | `/qa/comments/{comment_id}/vote` | MEMBER+ | Vote on answer (+1, -1, 0=remove) |

**Modified existing endpoints:**
- `POST /posts` — accept `type: 'post' | 'question'`
- `GET /posts` — accept `type` query filter
- Search — accept `type` filter

### 7.4 Vote Mechanics

**Toggle logic:**
| Current vote | Click Up | Click Down |
|-------------|----------|------------|
| None | +1 (delta +1) | -1 (delta -1) |
| +1 | remove (delta -1) | -1 (delta -2) |
| -1 | +1 (delta +2) | remove (delta +1) |

**Cannot vote on own answer** (service-level validation).

**Denormalized `vote_score`** on comments: updated atomically with the vote upsert.

### 7.5 Best Answer

- `posts.best_answer_id` — single FK (at most one best answer)
- `comments.is_best_answer` — redundant flag for fast query sorting
- Marking new best answer atomically un-marks previous
- Deleting a best-answer comment auto-clears `posts.best_answer_id`

**Comment sort order for Q&A:**
```sql
ORDER BY cm.is_best_answer DESC, cm.vote_score DESC, cm.created_at ASC
```

### 7.6 Auto-Assignment Algorithm

On question creation (via event bus `question.created`):

```sql
SELECT p.user_id, COUNT(DISTINCT unnested_kw) AS overlap_count
FROM posts p, unnest(p.keywords) AS unnested_kw
WHERE p.is_deleted = false
  AND p.user_id != $1  -- exclude author
  AND unnested_kw = ANY($2::text[])  -- question keywords
GROUP BY p.user_id
ORDER BY overlap_count DESC
LIMIT 5
```

**Rules:**
- Only runs if question has ≥ 1 keyword
- Max 5 invitations per question
- Redis key `qa_invite:{question_id}:{user_id}` (24h TTL) prevents re-inviting
- Notification: `action_type = 'QA_INVITE'`, can be ignored

### 7.7 Frontend

**New views:**
- `views/qa/QAListView.vue` — question listing (Answered/Unanswered badges, answer count, vote count)
- `views/qa/QACreateView.vue` — ask question form (reuses TipTap, categories, keywords)
- `views/qa/QADetailView.vue` — question + answers (best answer pinned, vote buttons)

**New components:**
- `components/qa/QACard.vue` — question card (vote count left, title center, answer count right)
- `components/qa/VoteButtons.vue` — vertical up/down arrows with score
- `components/qa/BestAnswerBadge.vue` — green checkmark badge

**Router:**
```typescript
{ path: '/qa', name: 'qa', component: QAListView, meta: { requiresAuth: true, fullWidth: true } }
{ path: '/qa/ask', name: 'qa-ask', component: QACreateView, meta: { requiresAuth: true } }
{ path: '/qa/:id', name: 'qa-detail', component: QADetailView, meta: { requiresAuth: true } }
```

**Modified:**
- `ForumView.vue` — pass `type: 'post'` to exclude questions
- `PostCard.vue` — link to `/qa/{id}` when `post.type === 'question'`
- `AppNavbar.vue` — add "Q&A" link

### 7.8 Business Rules

- **No post↔question conversion** (too complex, creates confusion)
- **Multiple best answers:** not allowed (single FK)
- **Guest access:** can view Q&A, cannot ask/answer/vote
- **answer_count:** only top-level comments (`parent_id IS NULL`), distinct from `comment_count`

---

## Cross-Feature Dependencies

```
Feature 1 (Forms) ────────────── independent
Feature 3 (Co-Authors) ────────── independent
Feature 7 (Q&A) ──────────────── independent
Feature 5 (Views/Citations) ──── independent
Feature 2 (Albums) ────────────── independent
Feature 4 (Social) ────────────── independent
Feature 6 (Recommendations) ──── depends on Feature 4 (friendships, blocks tables)
```

**Inter-feature interactions (post-implementation):**
- Feature 4 blacklist filtering must also apply to: Feature 2 album comments, Feature 7 Q&A answers, Feature 1 standalone form responses
- Feature 5 citations can cite Q&A questions (Feature 7)
- Feature 3 co-authors apply to Q&A questions (Feature 7)

---

## Complete File Inventory

### New Files Summary

| Feature | Backend | Frontend | Total New |
|---------|---------|----------|-----------|
| 1. Forms | 3 | 3 | 6 |
| 2. Albums | 7 | 12 | 19 |
| 3. Co-Authors | 10 | 4 | 14 |
| 4. Social | 6 | 8 | 14 |
| 5. Views/Citations | 7 | 4 | 11 |
| 6. Recommendations | 7 | 3 | 10 |
| 7. Q&A | 10 | 11 | 21 |
| **Total** | **50** | **45** | **95** |

### New Database Tables

| Table | Feature | Purpose |
|-------|---------|---------|
| (none — `sig_id` nullable) | 1 | Forms top-level |
| `albums` | 2 | Album metadata |
| `album_members` | 2 | Album membership |
| `album_photos` | 2 | Photo/ZIP storage |
| `album_comments` | 2 | Album comments |
| `post_co_authors` | 3 | Co-author junction |
| `friendships` | 4 | Friend relationships |
| `follows` | 4 | Follow relationships |
| `blocks` | 4 | Block relationships |
| `profile_views` | 5 | Profile view tracking |
| `post_citations` | 5 | Citation relationships |
| `friend_recommendations` | 6 | Precomputed recommendations |
| `dismissed_recommendations` | 6 | Dismissed recommendations |
| `comment_votes` | 7 | Answer voting |
| **Total: 13 new tables** | | |

### Alembic Migrations (7 total)

1. `make_form_sig_id_nullable.py` (Feature 1)
2. `add_album_tables.py` (Feature 2)
3. `add_post_co_authors_table.py` (Feature 3)
4. `add_social_relationships.py` (Feature 4)
5. `add_citations_and_profile_views.py` (Feature 5)
6. `add_friend_recommendations.py` (Feature 6)
7. `add_qa_feature.py` (Feature 7)

---

## Risk Assessment

### High Risk

| Risk | Feature | Mitigation |
|------|---------|------------|
| Blacklist filtering breaks existing queries | 4 | Test every filtered query independently; admin bypass |
| Concurrent post edits by co-authors | 3 | Existing optimistic locking handles it (409 conflict) |
| `str(None)` crash on nullable `sig_id` | 1 | Guard in converter; add unit test |

### Medium Risk

| Risk | Feature | Mitigation |
|------|---------|------------|
| Thumbnail generation failure | 2 | Celery retry (max 2); serve original if thumbnail missing |
| Vote score desync | 7 | Denormalized `vote_score` updated atomically; reconciliation task possible |
| Profile view counter drift | 5 | Celery Beat reconciliation every 6 hours |
| Recommendation SQL performance at scale | 6 | CTE-based single query; soft_time_limit=600s |
| Citation parsing regex misses edge cases | 5 | Test with varied HTML inputs; fallback gracefully |

### Low Risk

| Risk | Feature | Mitigation |
|------|---------|------------|
| Route ordering conflicts | 1,3,5,7 | Fixed paths always BEFORE parameterized `/{id}` routes |
| Redis memory for dedup keys | 5 | Estimated < 1 MB at scale; well within 256 MB limit |
| Max 5 blocks race condition | 4 | Redis lock during block operation |
| i18n key misses | All | Automated check in CI for missing keys |

### Performance Impact Summary

| Feature | DB Queries | Redis | CPU | Storage |
|---------|-----------|-------|-----|---------|
| 1. Forms | +2 queries (standalone list) | None | None | None |
| 2. Albums | +20 endpoint queries | Upload lock | Thumbnail gen (Celery) | Photos in MinIO |
| 3. Co-Authors | +1 batch query per post list | None | None | None |
| 4. Social | +1 WHERE clause per content query | Block set reads | None | None |
| 5. Views | Dedup writes | Dedup keys (24h TTL) | Citation parse (regex) | None |
| 6. Recommendations | Daily CTE batch (heavy, once/day) | None | Daily Celery task | None |
| 7. Q&A | +type filter (indexed) | Expert invite dedup | None | None |

---

## Appendix A: Cross-Audit Findings (5-Agent Review)

> Reviewed 2026-03-15 by 5 parallel audit agents covering: DB Schema, API Endpoints, Frontend, Cross-Feature, Security

### Summary

| Category | CRITICAL | HIGH | MEDIUM | LOW | Total |
|----------|----------|------|--------|-----|-------|
| DB Schema | 3 | 10 | 14 | 7 | 34 |
| API Endpoints | 5 | 13 | 19 | 11 | 48 |
| Frontend | 12 | 22 | 28 | 7 | 69 |
| Cross-Feature | 5 | 24 | 26 | 5 | 60 |
| Security | 1 | 12 | 17 | 9 | 39 |
| **Total (deduplicated)** | **~15** | **~40** | **~60** | **~25** | **~140** |

---

### A.1 CRITICAL Issues (Must Fix Before Implementation)

#### C-01: nginx body size limit blocks album ZIP uploads
`nginx.conf` sets `client_max_body_size 10m` and `main.py` sets `MAX_REQUEST_BODY_SIZE = 10MB`. Album ZIP uploads allow 100MB. Any upload > 10MB will be rejected with 413.

**Fix:** Add location-specific override in nginx for album upload endpoints:
```nginx
location ~ ^/api/v1/albums/.*/files {
    client_max_body_size 110m;
    proxy_pass ...;
}
```
Also increase `MAX_REQUEST_BODY_SIZE` conditionally or add a per-route override in FastAPI middleware.

#### C-02: Alembic migration chain unspecified — multiple heads will crash
All 7 migrations reference `down_revision = 'z7a8b9c0d1e2'` (current head). Alembic rejects multiple heads unless explicitly merged. Running `alembic upgrade head` will fail.

**Fix:** Chain migrations sequentially:
```
z7a8b9c0d1e2 → migration_1 → migration_2 → ... → migration_7
```
Migration 6 (recommendations) MUST come after migration 4 (social tables).

#### C-03: `anonymize_user()` does not clean up 13 new tables (GDPR risk)
The existing `anonymize_user()` only updates the `users` table. New tables (`friendships`, `follows`, `blocks`, `album_members`, `album_photos`, `album_comments`, `post_co_authors`, `profile_views`, `friend_recommendations`, `dismissed_recommendations`, `comment_votes`) are not cleaned up. Many FKs lack `ON DELETE CASCADE`.

**Fix:** Extend `anonymize_user()` to explicitly delete/anonymize records in all new tables. Add `ON DELETE CASCADE` where appropriate:
- `friendships`, `follows`, `blocks` → `ON DELETE CASCADE` on both user FK columns
- `album_members`, `album_comments` → `ON DELETE CASCADE` on `user_id`
- `album_photos.uploaded_by` → `ON DELETE SET NULL` (preserve photos, anonymize uploader)
- `post_co_authors.display_name` → anonymize to match `Deleted_User_xxx` pattern

#### C-04: `albums` table missing `is_deleted` column for soft-delete
The plan uses `is_archived` but the endpoint says "Soft-delete album." Every other table uses `is_deleted BOOLEAN NOT NULL DEFAULT false`. The two concepts (archive vs delete) are conflated.

**Fix:** Add both columns: `is_deleted BOOLEAN NOT NULL DEFAULT false` for soft-delete AND `is_archived BOOLEAN NOT NULL DEFAULT false` for archive. Or pick one semantic and be consistent.

#### C-05: Missing Pydantic response schemas for Features 2, 3, 4, 5, 6, 7
The plan defines endpoints but omits the Pydantic schemas needed for `response_model`. Without schemas: no type checking, no OpenAPI docs, no frontend type generation.

**Fix:** Define for each feature:
- **F2:** `AlbumResponse`, `AlbumListResponse`, `AlbumPhotoResponse`, `AlbumMemberResponse`, `AlbumCommentResponse`
- **F3:** `CoAuthorResponse`, `CoAuthorListResponse`, `CoAuthorInvitationResponse`, `CoAuthoredPostsListResponse`
- **F4:** `FriendshipResponse`, `FriendListResponse`, `FriendRequestListResponse`, `FollowUserListResponse`, `BlockListResponse`, `RelationshipStatusResponse`, `FriendRequestCreateRequest`
- **F5:** `CitationEntryResponse`, `CitationListResponse`
- **F6:** `RecommendedUserResponse`, `RecommendationsListResponse`, `DismissRequest`
- **F7:** `MarkBestAnswerRequest`, `VoteRequest`

#### C-06: Friendship UNIQUE constraint allows duplicate asymmetric entries
`UNIQUE (requester_id, addressee_id)` allows both `(A, B)` and `(B, A)` in the DB. Two concurrent requests can create conflicting entries.

**Fix:** Add a functional unique index:
```sql
CREATE UNIQUE INDEX ix_friendships_pair ON friendships (
    LEAST(requester_id, addressee_id),
    GREATEST(requester_id, addressee_id)
);
```

#### C-07: Missing TypeScript types & API modules for multiple features
Features 2, 3, 4, 5, 6, 7 all need TypeScript type files and API modules that are not listed in the plan:
- `types/album.ts`, `types/social.ts`, `types/coauthor.ts` (or extend `post.ts`), `types/citation.ts`, `types/recommendation.ts`
- `api/albums.ts`, `api/social.ts`, `api/coauthors.ts`, `api/citations.ts`, `api/recommendations.ts`, `api/qa.ts`
- `types/index.ts` and `api/index.ts` barrel re-exports

#### C-08: Q&A vote endpoint route namespace inconsistency
`POST /qa/comments/{comment_id}/vote` breaks the nested pattern (`/posts/{post_id}/comments/{comment_id}`). The `/qa` router is never registered in `router.py`.

**Fix:** Either use `POST /posts/{post_id}/comments/{comment_id}/vote` (extends existing comments router) or explicitly register `/qa` router in `router.py`.

#### C-09: `post_co_authors` UNIQUE constraint ineffective for external co-authors
`UNIQUE (post_id, user_id)` allows multiple NULLs in PostgreSQL. Multiple external co-authors can be added to the same post without constraint violation.

**Fix:** Add a partial unique index for external co-authors:
```sql
CREATE UNIQUE INDEX ix_post_co_author_external ON post_co_authors (post_id, display_name, COALESCE(affiliation, ''))
    WHERE is_external = TRUE;
```

---

### A.2 HIGH Issues (Should Fix Before Implementation)

#### H-01: FK `ON DELETE` behaviors missing or inconsistent across all new tables

| Table.Column | Current | Should Be |
|-------------|---------|-----------|
| `albums.created_by` | None (RESTRICT) | `SET NULL` (nullable) |
| `album_photos.uploaded_by` | None (RESTRICT) | `SET NULL` (nullable) |
| `album_comments.user_id` | None (RESTRICT) | `CASCADE` |
| `post_co_authors.invited_by` | `CASCADE` | `SET NULL` (nullable) — CASCADE deletes attribution |
| `friendships.requester_id` | None (RESTRICT) | `CASCADE` |
| `friendships.addressee_id` | None (RESTRICT) | `CASCADE` |
| `follows.follower_id` | None (RESTRICT) | `CASCADE` |
| `follows.following_id` | None (RESTRICT) | `CASCADE` |
| `blocks.blocker_id` | None (RESTRICT) | `CASCADE` |
| `blocks.blocked_id` | None (RESTRICT) | `CASCADE` |

#### H-02: Missing indexes on social tables
```sql
-- friendships (missing)
CREATE INDEX ix_friendships_requester ON friendships(requester_id, status);
CREATE INDEX ix_friendships_addressee ON friendships(addressee_id, status);
-- follows (missing)
CREATE INDEX ix_follows_follower ON follows(follower_id);
CREATE INDEX ix_follows_following ON follows(following_id);
-- blocks (missing)
CREATE INDEX ix_blocks_blocker ON blocks(blocker_id);
CREATE INDEX ix_blocks_blocked ON blocks(blocked_id);
-- comment_votes (missing)
CREATE INDEX ix_comment_votes_user ON comment_votes(user_id);
```

#### H-03: `notifications.action_type` VARCHAR(20) near capacity
`CO_AUTHOR_RESPONSE` = 19 chars. Future types may exceed 20. **Fix:** Widen to `VARCHAR(50)` via migration.

#### H-04: `RelationshipStatusResponse.is_blocked_by` leaks block status
Telling user B that A blocked them defeats the purpose. **Fix:** Remove `is_blocked_by` from the public API. Return 404 when blocked.

#### H-05: Follower notification fan-out unbounded
No cap like `_SIG_NOTIFICATION_MAX = 500` for follower notifications. A popular user posting could trigger 1000+ notifications in the FastAPI event loop.
**Fix:** Add `_FOLLOWER_NOTIFICATION_MAX = 500` and `_FOLLOWER_NOTIFICATION_CONCURRENCY = 20` semaphore.

#### H-06: Follow + SIG notification deduplication not implemented
A user who follows someone AND is in the same SIG receives two notifications for one post. The Redis idempotency key uses different action types so dedup does not trigger.
**Fix:** Use entity-level dedup key: `notify:idempotent:{user_id}:post:{post_id}:new_post` (drop the action from the key).

#### H-07: `TRUNCATE friend_recommendations` blocks concurrent reads
`TRUNCATE` acquires `ACCESS EXCLUSIVE` lock. **Fix:** Use `DELETE FROM` inside a transaction, or staging-table swap.

#### H-08: Blacklist filtering must also cover Features 1, 2, 7 content
The plan lists blacklist filtering for existing tables but omits:
- `album_comments` (uploaded_by/user_id)
- `album_photos` display (hide photos from blocked users)
- Q&A answers (`comment_repo.find_many` with `sort_by_votes`)
- Standalone form responses
- Co-author invitations (cannot invite a user who blocked you)
- Citation notifications (skip if cited author blocked citer)
- Friend recommendations (exclude blocked users)

#### H-09: IDOR risks — missing explicit ownership checks
Several endpoints say "MEMBER+" auth but require ownership:
- `POST /posts/{post_id}/co-authors/invite` — must verify post ownership
- `POST /qa/{post_id}/best-answer` — must verify question authorship
- `PUT /albums/{id}/photos/{pid}` — must verify photo ownership

#### H-10: `nh3` sanitizer `class` attribute on `<a>` opens CSS injection
nh3 does not support value-level filtering. Adding `class` allows arbitrary CSS class injection.
**Fix:** Do NOT add `class` to nh3 allowed attrs. Instead, post-process the sanitized HTML to inject `class="citation"` only on links that have `data-citation="true"`.

#### H-11: Citation parsing should use HTML parser, not regex
Regex on HTML is fragile and susceptible to ReDoS. **Fix:** Use Python's `html.parser` or `lxml.html` to extract `<a data-citation="true">` elements.

#### H-12: Missing magic bytes for WebP/GIF in `file_validation.py`
Album uploads allow WebP/GIF but `MAGIC_NUMBERS` only has JPEG/PNG/PDF/DOCX signatures.
**Fix:** Add WebP (`RIFF....WEBP`) and GIF (`GIF87a`/`GIF89a`) magic bytes.

#### H-13: No admin endpoints for album/Q&A management
- No admin album view (force-delete, view all, storage stats)
- No admin Q&A controls (close question, remove best answer)

#### H-14: Missing notification events
- `album.comment.created` — no event defined
- `best_answer.marked` — no event/notification for answer author
- `album.join_request` — no notification for album admin
- `album.join_approved` — no notification for requester

#### H-15: 3 denormalized counters have no reconciliation tasks
- `posts.citation_count` — no Celery Beat reconciliation
- `posts.answer_count` — no reconciliation
- `comments.vote_score` — no reconciliation

**Fix:** Add a single reconciliation Celery Beat task (every 6 hours) covering all 3.

#### H-16: Profile view counter updates are non-atomic
`record_profile_view()` calls 3 separate DB operations. Crash between steps causes permanent drift until reconciliation.
**Fix:** Wrap all 3 operations in a single transaction.

#### H-17: All social endpoints missing rate limits
13 social endpoints have no rate limits. Friend request/follow/block spam can generate notification storms.
**Fix:** Add `RATE_LIMIT_SOCIAL = _rate_limit("SOCIAL", 30, 60)`.

#### H-18: Vote endpoint missing rate limit
**Fix:** Add `RATE_LIMIT_VOTE = _rate_limit("VOTE", 60, 60)`.

#### H-19: nginx write-zone rate limit regex doesn't cover new prefixes
Only matches `^/api/v1/(posts|comments|forms)`. **Fix:** Extend to include `albums|social|qa|recommendations|co-authors`.

#### H-20: Celery task modules not added to `include` list
`tasks/thumbnail.py`, `tasks/recommendations.py`, `tasks/view_sync.py` all need adding to `celery_app.py` includes.

#### H-21: New router registrations missing from `router.py`
Features 2 (albums), 4 (social), 6 (recommendations), 7 (qa) create new endpoint files but don't specify `include_router` in `router.py`.

#### H-22: `posts.type` missing CHECK constraint
**Fix:** Add `CHECK (type IN ('post', 'question'))`.

#### H-23: Soft-delete doesn't trigger FK `ON DELETE SET NULL` for best_answer_id
Comments are soft-deleted (`is_deleted = true`), not hard-deleted. `posts.best_answer_id` FK's `ON DELETE SET NULL` only fires on hard delete.
**Fix:** Service layer must explicitly clear `best_answer_id` when soft-deleting a best-answer comment.

#### H-24: No audit logging for admin social/album actions
Album create/delete and block management are admin actions that should be audit-logged.

---

### A.3 MEDIUM Issues (Fix During Implementation)

**DB/Backend:**
1. `RATE_LIMIT_ALBUM_UPLOAD` uses wrong tuple format — should use `_rate_limit()` helper
2. `profile_views.idx_profile_views_profile_id` redundant with the UNIQUE index
3. No `updated_at` on `follows`, `blocks`, `comment_votes` tables (inconsistent with project convention)
4. `post_co_authors.status` no CHECK constraint enforcing `is_external=TRUE → status='ACCEPTED'`
5. `posts.type VARCHAR(20)` may be too narrow — use VARCHAR(30)
6. No `post_citations.updated_at` column (project convention)
7. `recommendations.reasons` JSONB schema undocumented
8. Block cascade: Redis update after DB commit creates brief stale-cache window
9. `build_block_exclusion_clause()` should validate `user_column` against allowlist
10. Citation search endpoint duplicates existing search — consider reusing with param
11. `comments.vote_score` can go negative — no floor constraint
12. Album comments not sanitized via `sanitize_html()`
13. No album archive/unarchive endpoint
14. No album cover photo set endpoint
15. No album pending join request list/reject endpoints
16. No album comment edit endpoint
17. Missing pagination on album comments and social list endpoints
18. Q&A answer sort order not configurable via endpoint parameter
19. `FormListResponse` missing `current_page`/`total_pages` pagination fields
20. `GET /forms` public access may conflict with CSRF middleware
21. Co-author re-invitation after rejection not addressed
22. User search endpoint (`GET /users/search`) overlaps with admin `GET /users`
23. Album search (by title/description) not supported
24. Full-text search `post_repo.search()` missing `type` filter parameter
25. Concurrent vote toggle can corrupt `vote_score` — use atomic upsert

**Frontend:**
26. Mobile nav menu needs updating for ALL new top-level features
27. `useFormBuilder.ts` type signature: `sigId: () => string` must become `() => string | undefined`
28. All new views missing loading/error/empty state specifications
29. All new views missing breadcrumb specifications
30. No `AlbumCreateView` or creation modal specified
31. Album edit/archive UI not specified
32. PhotoLightbox missing keyboard nav and accessibility
33. PhotoGrid missing responsive breakpoint spec
34. No ZIP download UI component
35. `usePostDetail.ts` `canModify` logic for co-authors underspecified
36. ProfileView "Invitations" tab not detailed
37. UserProfileView "Co-Authored Posts" tab requires restructuring
38. VoteButtons toggle state management underspecified
39. `ForumView` must pass `type: 'post'` simultaneously with backend change to prevent mixed content
40. Regular post comments should hide vote UI (`vote_score` column exists on all comments)
41. Recommendation reasons JSONB must be structured (type+params), not pre-formatted English strings, for i18n
42. `assertShape<T>()` not mentioned for any new API functions
43. `api/index.ts` and `types/index.ts` barrel exports need updating
44. 17 locale files need keys for all 7 features (estimated 200+ new keys)
45. Mobile menu `max-height: 500px` may clip with new nav items

---

### A.4 Action Items per Feature

#### Feature 1 (Forms Top-Level) — 3 fixes needed
- [ ] Fix route ordering in `router/index.ts` (before existing `/forms/:formId`)
- [ ] Add rate limit to `POST /forms`
- [ ] Fix `useFormBuilder` type signature (`sigId: () => string | undefined`)

#### Feature 2 (Activity Albums) — 12 fixes needed
- [ ] Add `is_deleted` column to `albums` table
- [ ] Fix nginx `client_max_body_size` for ZIP uploads
- [ ] Add `ON DELETE SET NULL` on `created_by`, `uploaded_by`
- [ ] Add WebP/GIF magic bytes to `file_validation.py`
- [ ] Add Pillow `MAX_IMAGE_PIXELS` guard in thumbnail task
- [ ] Define ALL Pydantic response schemas
- [ ] Define ALL TypeScript types and API module
- [ ] Add album creation view/modal
- [ ] Add album edit/archive UI
- [ ] Add pending request list + reject endpoint
- [ ] Add album comment edit endpoint
- [ ] Add album notification events (join request, comment reply)

#### Feature 3 (Co-Authors) — 6 fixes needed
- [ ] Fix `invited_by` FK: `ON DELETE SET NULL` instead of CASCADE
- [ ] Add ORCID format validation
- [ ] Add explicit ownership check on invite endpoint
- [ ] Define ALL TypeScript types and API module
- [ ] Fix UNIQUE constraint for external co-authors (partial index)
- [ ] Specify co-author self-removal mechanism

#### Feature 4 (Social) — 9 fixes needed
- [ ] Add bidirectional friendship UNIQUE index (`LEAST/GREATEST`)
- [ ] Add `ON DELETE CASCADE` on ALL social table FKs
- [ ] Add ALL missing indexes
- [ ] Remove `is_blocked_by` from public API
- [ ] Add rate limits to ALL social endpoints
- [ ] Cap follower notifications at 500
- [ ] Add notification dedup between follow and SIG
- [ ] Define ALL Pydantic response schemas
- [ ] Extend `anonymize_user()` for social cleanup + Redis cache clear

#### Feature 5 (Views/Citations) — 6 fixes needed
- [ ] Use HTML parser instead of regex for citation extraction
- [ ] Do NOT add `class` to nh3 `<a>` attrs; post-process instead
- [ ] Add WebP/GIF magic bytes (shared with Feature 2)
- [ ] Wrap profile view counter updates in transaction
- [ ] Add `citation_count` reconciliation Celery task
- [ ] Define citation response schemas

#### Feature 6 (Recommendations) — 4 fixes needed
- [ ] Replace `TRUNCATE` with `DELETE` + `INSERT` in transaction
- [ ] Document JSONB `reasons` schema for i18n compatibility
- [ ] Add rate limits
- [ ] Add concurrency guard (Redis lock)

#### Feature 7 (Q&A) — 7 fixes needed
- [ ] Add `CHECK (type IN ('post', 'question'))` constraint
- [ ] Register `/qa` router in `router.py`
- [ ] Add explicit question-author check on best-answer endpoint
- [ ] Use atomic SQL for vote upsert + score update
- [ ] Service layer must clear `best_answer_id` on soft-delete (FK only triggers on hard delete)
- [ ] Add `answer_count` + `vote_score` reconciliation task
- [ ] Hide vote UI on regular post comments (frontend)

#### Cross-Feature — 8 fixes needed
- [ ] Chain all 7 migrations sequentially in Alembic
- [ ] Extend `anonymize_user()` for ALL 13 new tables
- [ ] Add blacklist filtering to album comments, Q&A, standalone forms, citations, recommendations
- [ ] Widen `notifications.action_type` to VARCHAR(50)
- [ ] Update nginx write-zone regex for new API prefixes
- [ ] Add ALL new Celery task modules to `celery_app.py` includes
- [ ] Register ALL new routers in `router.py`
- [ ] Define feature-specific `ErrorCode` enum values
