# Multi-Agent Implementation Strategy

> Generated: 2026-03-15 | Based on: `docs/feature-implementation-plan.md` + Appendix A audit

## 1. Executive Summary

**Scope:** 7 features, ~95 new files, ~100 modified files, 13 new DB tables, ~140 audit fixes
**Strategy:** 7 phases, 13 agent invocations, max 4 agents parallel per phase
**Core constraint:** No two parallel agents may modify the same file

| Phase | Agents | Parallel | Purpose |
|-------|--------|----------|---------|
| 0 | 1 | — | Shared infrastructure (migrations, schemas, types, constants) |
| 1 | 4 | Yes | Independent backend modules (F1, F2, F4-core, F6) |
| 2 | 1 | — | Post-system backend (F3 + F5 + F7) |
| 3 | 1 | — | Blacklist integration across all repos |
| 4 | 3 | Yes | Frontend modules |
| 5 | 1 | — | Frontend integration (navbar, router, i18n, shared views) |
| 6 | 2 | Yes | Quality assurance |
| **Total** | **13** | | |

---

## 2. Conflict Analysis

### 2.1 Why Not All Parallel?

Multiple features modify the same existing files. Running them in parallel (even in worktrees) creates merge conflicts that are hard to resolve correctly.

### 2.2 Backend Conflict Matrix

Which existing files each feature **modifies** (not creates):

```
                        F1   F2   F3   F4*  F5   F6   F7
─────────────────────────────────────────────────────────
repositories/form_repo    ✓              ✓b
converters/form_conv      ✓
services/form             ✓              ✓b
endpoints/forms           ✓              ✓b
core/deps                 ✓
core/storage                   ✓
services/post                       ✓    ✓b   ✓         ✓
event_handlers                      ✓    ✓    ✓         ✓
services/user                       ✓    ✓
endpoints/users                     ✓    ✓b   ✓
repositories/post_repo                   ✓b
repositories/comment_repo                ✓b
repositories/notif_repo                  ✓b
core/file_validation                          ✓
endpoints/posts                                         ✓
─────────────────────────────────────────────────────────
✓ = direct modification   ✓b = blacklist integration (Phase 3)
F4* = F4 has two parts: core (new files) and blacklist (modifies many)
```

**Non-conflicting backend groups:**
- `{F1, F2, F4-core, F6}` — zero file overlap (all modify different existing files or only create new ones)
- `{F3, F5, F7}` — conflict on `services/post.py`, `event_handlers.py` → must be sequential or single agent
- `{F4-blacklist}` — touches repos from ALL other features → must run last

### 2.3 Frontend Conflict Matrix

```
                        F1   F2   F3   F4   F5   F6   F7
─────────────────────────────────────────────────────────
AppNavbar               ✓    ✓              ✓         ✓
router/index.ts         ✓    ✓    ✓    ✓    ✓    ✓    ✓
PostCard                          ✓         ✓         ✓
PostDetailView                    ✓         ✓
usePostDetail                     ✓
ProfileView                       ✓    ✓
UserProfileView                   ✓    ✓    ✓    ✓
HomeView                                         ✓
ForumView                                             ✓
FormBuilderView         ✓
FormView                ✓
useFormBuilder          ✓
useFormSubmit           ✓
useFormDraft            ✓
TiptapEditor                                ✓
─────────────────────────────────────────────────────────
```

**Non-conflicting frontend groups:**
- `{F1+F2}` — F1 only touches form files, F2 only creates new album files (only AppNavbar overlap → deferred to Phase 5)
- `{F4+F6}` — F4 creates social views, F6 creates recommendation widget + HomeView (only UserProfileView overlap → deferred to Phase 5)
- `{F3+F5+F7}` — conflict on PostCard, PostDetailView → single agent
- **Shared files** (`AppNavbar`, `router/index.ts`, `ProfileView`, `UserProfileView`) → deferred to Phase 5 integration agent

---

## 3. Phase Details

### Phase 0: Foundation Infrastructure

**Agent 0 — `foundation`**

Creates ALL shared infrastructure that multiple features depend on, preventing merge conflicts in later phases.

**Creates:**
| File | Purpose |
|------|---------|
| `backend/alembic/versions/xxxx_01_forms_standalone.py` | F1: sig_id nullable |
| `backend/alembic/versions/xxxx_02_albums.py` | F2: 4 album tables |
| `backend/alembic/versions/xxxx_03_co_authors.py` | F3: post_co_authors |
| `backend/alembic/versions/xxxx_04_social.py` | F4: friendships, follows, blocks |
| `backend/alembic/versions/xxxx_05_views_citations.py` | F5: profile_views, post_citations, denormalized counters |
| `backend/alembic/versions/xxxx_06_recommendations.py` | F6: friend_recommendations, dismissed_recommendations |
| `backend/alembic/versions/xxxx_07_qa.py` | F7: posts.type, comments.vote_score, comment_votes |
| `backend/app/schemas/album.py` | AlbumResponse, AlbumPhotoResponse, etc. |
| `backend/app/schemas/co_author.py` | CoAuthorResponse, InvitationResponse, etc. |
| `backend/app/schemas/social.py` | FriendshipResponse, RelationshipStatusResponse, etc. |
| `backend/app/schemas/citation.py` | CitationEntryResponse, etc. |
| `backend/app/schemas/recommendation.py` | RecommendedUserResponse, etc. |
| `backend/app/schemas/qa.py` | VoteRequest, MarkBestAnswerRequest |
| `frontend/src/types/album.ts` | Album, AlbumPhoto, AlbumMember, AlbumComment |
| `frontend/src/types/coauthor.ts` | CoAuthor, CoAuthorInvitation |
| `frontend/src/types/social.ts` | Friendship, Follow, Block, RelationshipStatus |
| `frontend/src/types/citation.ts` | Citation, CitationEntry |
| `frontend/src/types/recommendation.ts` | FriendRecommendation |
| `frontend/src/types/qa.ts` | Question (extends Post), CommentVote |
| `frontend/src/api/albums.ts` | API function stubs |
| `frontend/src/api/social.ts` | API function stubs |
| `frontend/src/api/coauthors.ts` | API function stubs |
| `frontend/src/api/citations.ts` | API function stubs |
| `frontend/src/api/recommendations.ts` | API function stubs |
| `frontend/src/api/qa.ts` | API function stubs |

**Modifies:**
| File | Change |
|------|--------|
| `backend/app/core/constants.py` | Add ALL feature constants (album limits, rate limits, co-author max, etc.) |
| `backend/app/core/errors.py` | Add ALL new ErrorCode enum values |
| `backend/app/api/v1/router.py` | Add `include_router` for albums, social, recommendations, qa |
| `backend/app/celery_app.py` | Add task includes + beat_schedule entries |
| `backend/app/core/file_validation.py` | Add WebP (`RIFF....WEBP`) + GIF (`GIF87a`/`GIF89a`) magic bytes |
| `backend/app/schemas/form.py` | `sig_id: str` → `str \| None` |
| `frontend/src/types/post.ts` | Add `type`, `best_answer_id`, `answer_count`, `citation_count` fields |
| `frontend/src/types/index.ts` | Add barrel re-exports |
| `frontend/src/api/index.ts` | Add barrel re-exports |

**Audit fixes incorporated:**
- **C-02:** Chain 7 migrations sequentially (each `down_revision` = previous migration)
- **C-04:** Add `is_deleted` column to `albums` table
- **C-05:** Define ALL Pydantic response schemas
- **C-06:** Add bidirectional friendship UNIQUE index (`LEAST/GREATEST`)
- **C-07:** Define ALL TypeScript types + API modules
- **C-09:** Add partial UNIQUE index for external co-authors
- **H-01:** Fix FK `ON DELETE` behaviors on all new tables
- **H-02:** Add all missing indexes on social tables
- **H-03:** Widen `notifications.action_type` to VARCHAR(50) (separate migration)
- **H-12:** Add WebP/GIF magic bytes
- **H-20:** Add Celery task modules to includes
- **H-21:** Register all new routers
- **H-22:** Add `CHECK (type IN ('post', 'question'))` on posts

**Verification after Phase 0:**
```bash
cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head  # migration chain works
cd backend && pytest tests/ -v  # existing tests still pass
cd frontend && npx tsc --noEmit  # new types compile
cd frontend && npx vite build   # build succeeds
```

---

### Phase 1: Independent Backend Modules (4 Parallel Agents)

These 4 agents create/modify entirely non-overlapping file sets.

#### Agent 1A — `forms-backend`

**Feature:** F1 (Forms Top-Level)
**Scope:** Small (~6 files)

**Modifies:**
- `repositories/form_repo.py` — add `find_standalone()`, `count_active_by_user()`
- `converters/form_converter.py` — fix `str(row["sig_id"])` crash when None
- `services/form.py` — standalone form logic, per-user limit, skip SIG checks
- `endpoints/forms.py` — `POST /forms`, `GET /forms`, modify `GET /forms/{id}` for public access
- `core/deps.py` — add `get_optional_current_user()` helper

**Creates:**
- `tests/test_standalone_forms.py` — ~14 test cases

**Audit fixes:** Rate limit on `POST /forms`, route ordering

**Key instructions for agent:**
> Read `endpoints/forms.py`, `services/form.py`, `repositories/form_repo.py`, `converters/form_converter.py`, `core/deps.py` first. Schemas already created in Phase 0. Constants already in `constants.py`. Route ordering: `POST /forms` and `GET /forms` BEFORE `GET /forms/{form_id}`.

---

#### Agent 1B — `albums-backend`

**Feature:** F2 (Activity Albums)
**Scope:** Large (~8 new files)

**Creates:**
- `repositories/album_repo.py` — all album SQL queries (CRUD, members, photos, comments)
- `converters/album_converter.py` — row→schema conversion
- `services/album.py` — business logic (upload flow, quota check, permissions)
- `endpoints/albums.py` — all 19 album endpoints
- `tasks/thumbnail.py` — Celery task for Pillow thumbnail generation

**Modifies:**
- `core/storage.py` — add `album_photo_key()`, `album_thumbnail_key()`, `album_zip_key()`

**Creates (tests):**
- `tests/test_albums.py` — ~25 test cases

**Audit fixes:**
- Pillow `MAX_IMAGE_PIXELS` guard in thumbnail task
- Album comment `sanitize_html()` call
- H-14: Define notification events (album.comment, album.join_request, album.join_approved)
- M-13/14/15: Archive, cover photo, join reject endpoints

**Key instructions for agent:**
> Read `core/storage.py`, `services/post.py` (for upload pattern reference), `core/file_validation.py` (for magic byte validation pattern). Schemas already in `schemas/album.py`. Constants already in `constants.py`. Tables already created by migration. Use existing `get_storage_used()` / `increment_storage_used()` / `decrement_storage_used()` from `repositories/user_repo.py` for quota management. Use `check_rate_limit()` pattern from existing endpoints.

---

#### Agent 1C — `social-core-backend`

**Feature:** F4a (Social Core — friendships, follows, blocks, Redis cache)
**Scope:** Medium (~6 new files)
**NOT including:** Blacklist integration into existing repos (that's Phase 3)

**Creates:**
- `repositories/social_repo.py` — friendship/follow/block CRUD, relationship status queries
- `converters/social_converter.py` — row→schema
- `services/social.py` — block cascade (unfriend+unfollow+Redis), friend request dedup, max-5 enforcement
- `endpoints/social.py` — all 13 social endpoints
- `core/blacklist.py` — Redis cache helpers (`get_blocked_user_ids()`, `warmup_block_cache()`, `build_block_exclusion_clause()`)

**Creates (tests):**
- `tests/test_social.py` — ~20 test cases
- `tests/test_blacklist_cache.py` — ~8 test cases

**Audit fixes:**
- H-04: Remove `is_blocked_by` from `RelationshipStatusResponse`
- H-17: Rate limits on all 13 social endpoints (`RATE_LIMIT_SOCIAL`)
- Block cascade in single transaction
- Max-5 enforcement with Redis lock
- Duplicate friend request → auto-accept
- `warmup_block_cache()` called in app startup

**Key instructions for agent:**
> Read `event_handlers.py` (for event bus pattern), `core/redis.py`, `services/user.py` (for anonymize pattern). Schemas already in `schemas/social.py`. Do NOT modify existing repos for blacklist filtering — that's Phase 3. Only create the blacklist helpers in `core/blacklist.py`. Add `warmup_block_cache()` call to `main.py` lifespan.

---

#### Agent 1D — `recommendations-backend`

**Feature:** F6 (Friend Recommendations)
**Scope:** Small (~5 new files)

**Creates:**
- `repositories/recommendation_repo.py` — precomputed recommendations CRUD, dismissed CRUD
- `services/recommendation.py` — get recommendations (exclude dismissed), dismiss
- `endpoints/recommendations.py` — `GET /recommendations/friends`, `POST /recommendations/friends/dismiss`
- `tasks/recommendations.py` — daily Celery Beat task with CTE-based scoring SQL

**Creates (tests):**
- `tests/test_recommendations.py` — ~10 test cases

**Audit fixes:**
- H-07: Use `DELETE FROM` + `INSERT` in transaction (not `TRUNCATE`)
- Rate limits on endpoints
- Redis lock to prevent concurrent task runs
- JSONB `reasons` schema: `[{"type": "common_sig", "sig_name": "..."}, ...]` (structured for i18n)

**Key instructions for agent:**
> Read `celery_app.py` (for task pattern), `tasks/cleanup.py` (for Celery task example). Tables already created by migration. Beat schedule entry already added in Phase 0. Task module already in includes list. The scoring SQL uses CTEs joining `friendships`, `follows`, `sig_members`, `posts` tables. Minimum user count check (>10) before running.

---

### Phase 1 Verification

```bash
cd backend && pytest tests/ -v            # all tests pass (existing + new)
cd backend && isort app/ tests/ --check    # import ordering
cd backend && mypy app/                    # type checking
```

---

### Phase 2: Post-System Backend (1 Agent)

#### Agent 2 — `post-extensions-backend`

**Features:** F3 (Co-Authors) + F5 (Views/Citations) + F7 (Q&A)
**Scope:** Large (~15 new files, ~5 modified files)

**Why one agent:** All three modify `services/post.py`, `event_handlers.py`, and `endpoints/users.py`. Running in parallel would create unresolvable merge conflicts.

**Creates:**
| File | Feature | Purpose |
|------|---------|---------|
| `repositories/co_author_repo.py` | F3 | Co-author CRUD, `is_accepted_co_author()`, batch fetch |
| `converters/co_author_converter.py` | F3 | Row→schema |
| `services/co_author.py` | F3 | Invite, respond, remove, limit enforcement |
| `endpoints/co_authors.py` | F3 | 4 post-scoped + 4 user-scoped endpoints |
| `repositories/citation_repo.py` | F5 | Citation CRUD, citing/cited queries |
| `repositories/profile_view_repo.py` | F5 | Upsert view, counter queries |
| `services/citation.py` | F5 | `sync_post_citations()` with HTML parser |
| `services/profile_view.py` | F5 | `record_profile_view()` in single transaction |
| `tasks/view_sync.py` | F5 | Reconciliation task (profile + citation + answer + vote counters) |
| `repositories/vote_repo.py` | F7 | Atomic vote upsert + score update |
| `services/qa.py` | F7 | Best answer mark/unmark, vote toggle, auto-assignment |
| `endpoints/qa.py` | F7 | 3 Q&A-specific endpoints |

**Modifies:**
| File | Changes |
|------|---------|
| `services/post.py` | (F3) Add co-author permission check in `update_post()`. (F5) Change Redis view dedup TTL 300→86400. (F7) Add `type` filter to queries, `answer_count` update on comment create. |
| `event_handlers.py` | (F3) `co_author.invited`, `co_author.responded`. (F5) `post.cited`. (F7) `question.created` → auto-assignment. |
| `services/user.py` | (F3) Add co-author anonymize. (F5) Profile view cleanup. |
| `endpoints/users.py` | (F3) `GET /users/search`, `GET /users/me/co-author-invitations/*`. (F5) Record profile view on `GET /users/{id}`. |
| `endpoints/posts.py` | (F7) Accept `type` query param. |

**Creates (tests):**
- `tests/test_co_authors.py` — ~15 cases
- `tests/test_citations.py` — ~12 cases
- `tests/test_profile_views.py` — ~8 cases
- `tests/test_qa.py` — ~18 cases
- `tests/test_votes.py` — ~10 cases

**Audit fixes:**
- **C-08:** Register `/qa` router OR use `/posts/{id}/qa/...` namespace
- **H-09:** Explicit ownership checks (co-author invite → post owner, best-answer → question author)
- **H-10:** Do NOT add `class` to nh3 allowed attrs; post-process sanitized HTML for citation class
- **H-11:** Use `html.parser` (stdlib) for citation extraction, not regex
- **H-15:** Single reconciliation task in `tasks/view_sync.py` covering `citation_count`, `answer_count`, `vote_score`, `profile_view_count_*`
- **H-16:** Wrap profile view operations in single DB transaction
- **H-18:** Vote rate limit
- **H-23:** Service layer clears `best_answer_id` when soft-deleting a best-answer comment
- **M-25:** Atomic SQL for vote upsert + `vote_score` update (single statement with CTE)

**Key instructions for agent:**
> Read ALL files you need to modify FIRST: `services/post.py`, `event_handlers.py`, `services/user.py`, `endpoints/users.py`, `endpoints/posts.py`. Read `core/event_bus.py` for event pattern. Read `services/comment.py` for comment creation flow (needed for answer_count). Schemas already exist in Phase 0 files. Route ordering: `/users/search` and `/users/me/*` BEFORE `/{user_id}`.

---

### Phase 2 Verification

```bash
cd backend && pytest tests/ -v
cd backend && isort app/ tests/ --check
cd backend && mypy app/
```

---

### Phase 3: Blacklist Integration (1 Agent)

#### Agent 3 — `blacklist-integration`

**Purpose:** Wire F4's blacklist filtering into ALL content repositories and services.
**Scope:** Medium-large (~15 modified files)

**Modifies:**
| File | Change |
|------|--------|
| `repositories/post_repo.py` | Add `exclude_user_ids: list[uuid.UUID] \| None` param to `find_many()`, `search()`, `find_trending()` → `AND p.user_id != ALL($N::uuid[])` |
| `repositories/comment_repo.py` | Add `exclude_user_ids` to `find_many()` |
| `repositories/notification_repo.py` | Add `exclude_user_ids` to `find_many()` |
| `repositories/form_repo.py` | Add `exclude_user_ids` to `find_responses()` |
| `repositories/album_repo.py` | Add `exclude_user_ids` to album comments + photo queries |
| `services/post.py` | Call `get_blocked_user_ids()`, pass to repo in all list/search operations |
| `services/comment.py` | Block check on `create_comment()`, pass blocked IDs to repo |
| `services/notification.py` | Filter notifications from blocked users, suppress blocked-user notifications |
| `services/form.py` | Block check on `submit_response()`, filter `list_form_responses()` |
| `services/album.py` | Filter album comments from blocked users |
| `services/co_author.py` | Block check on invite (cannot invite blocked user) |
| `endpoints/posts.py` | Pass `current_user["id"]` to service for block filtering |
| `endpoints/comments.py` | Pass viewer context |
| `endpoints/notifications.py` | Pass viewer context |
| `endpoints/forms.py` | Pass viewer context for response filtering |
| `endpoints/users.py` | Return 404 for blocked user profile |
| `endpoints/sigs.py` | Pass viewer ID for SIG posts filtering |
| `event_handlers.py` | Block check before ALL notification events |
| `nginx/conf.d.dev/default.conf` | Update write-zone regex to include new prefixes |

**Audit fixes:**
- **H-05:** Cap follower notifications at 500 (`_FOLLOWER_NOTIFICATION_MAX = 500`)
- **H-06:** Entity-level notification dedup key: `notify:idempotent:{user_id}:post:{post_id}:new_post`
- **H-08:** Blacklist filtering across all features
- **H-19:** Extend nginx write-zone regex: `^/api/v1/(posts|comments|forms|albums|social|qa|recommendations)`
- **H-24:** Audit logging for admin social/album actions

**Creates (tests):**
- `tests/test_blacklist_integration.py` — ~15 cases covering all filtered queries

**Key instructions for agent:**
> Read `core/blacklist.py` (created in Phase 1C) for `get_blocked_user_ids()` and `build_block_exclusion_clause()`. Read EVERY repo and service you need to modify. Pattern: in service layer, call `blocked_ids = await get_blocked_user_ids(user_id)`, then pass to repo as `exclude_user_ids=list(blocked_ids)`. In repo, if `exclude_user_ids` is not empty, append `AND {column} != ALL($N::uuid[])` to WHERE clause. For single-item fetches (post detail, profile), do post-fetch check instead.

---

### Phase 3 Verification

```bash
cd backend && pytest tests/ -v         # ALL backend tests pass
cd backend && isort app/ tests/ --check
cd backend && mypy app/
```

**Full backend is now complete. Commit checkpoint.**

---

### Phase 4: Frontend Modules (3 Parallel Agents)

These 3 agents work on non-overlapping file sets. Shared files (`AppNavbar`, `router/index.ts`, `ProfileView`, `UserProfileView`) are deferred to Phase 5.

#### Agent 4A — `forms-albums-frontend`

**Features:** F1 + F2 frontend
**Scope:** Large (~13 new files, ~5 modified files)

**Creates:**
| File | Purpose |
|------|---------|
| `views/forms/FormsDirectoryView.vue` | Paginated grid of standalone forms |
| `views/albums/AlbumsDirectoryView.vue` | Album listing grid |
| `views/albums/AlbumLayout.vue` | Parent layout (provide/inject, like SigLayout) |
| `views/albums/AlbumPhotosView.vue` | Photo grid child view |
| `views/albums/AlbumMembersView.vue` | Members management child view |
| `views/albums/AlbumCommentsView.vue` | Threaded comments child view |
| `views/albums/AlbumCreateView.vue` | Album creation form (ADMIN only) |
| `components/albums/AlbumCard.vue` | Card for directory listing |
| `components/albums/PhotoGrid.vue` | Responsive thumbnail grid |
| `components/albums/PhotoUploadModal.vue` | Upload with quota display |
| `components/albums/PhotoLightbox.vue` | Full-size viewer with keyboard nav |
| `composables/useAlbumLayout.ts` | Typed inject wrapper (like useSigLayout) |

**Modifies:**
| File | Change |
|------|--------|
| `views/forms/FormBuilderView.vue` | Standalone mode: breadcrumb, hide `allowNonMembers` |
| `views/forms/FormView.vue` | Standalone breadcrumb, "Back to Forms" button |
| `composables/useFormBuilder.ts` | `isStandalone` computed, `sigId: () => string \| undefined` type fix |
| `composables/useFormSubmit.ts` | Guard `getSig()`, standalone redirect to `/forms` |
| `composables/useFormDraft.ts` | `'form-draft-unknown'` → `'form-draft-standalone'` |

**Does NOT modify:** `AppNavbar.vue`, `router/index.ts` (deferred to Phase 5)

**Audit fixes:** M-27 (useFormBuilder type), M-30 (album create), M-32 (lightbox keyboard nav), M-33 (responsive breakpoints)

---

#### Agent 4B — `social-recs-frontend`

**Features:** F4 + F6 frontend
**Scope:** Medium (~8 new files, ~1 modified file)

**Creates:**
| File | Purpose |
|------|---------|
| `views/social/FriendsView.vue` | Friends list + pending requests |
| `views/social/FollowingView.vue` | Following/followers tabs |
| `views/social/BlockedUsersView.vue` | Blocked users management |
| `components/social/SocialActions.vue` | Follow/Friend/Block button group |
| `components/social/FriendRequestCard.vue` | Accept/reject UI |
| `components/social/FriendRecommendations.vue` | Sidebar widget (avatar, name, reasons, dismiss) |
| `composables/useSocialStatus.ts` | Fetch + cache relationship status |

**Modifies:**
| File | Change |
|------|--------|
| `views/HomeView.vue` | Add FriendRecommendations sidebar (right side, authenticated non-guest only) |

**Does NOT modify:** `UserProfileView.vue`, `ProfileView.vue`, `AppNavbar.vue`, `router/index.ts` (deferred to Phase 5)

**Audit fixes:** M-41 (i18n-compatible structured reasons display)

---

#### Agent 4C — `post-extensions-frontend`

**Features:** F3 + F5 + F7 frontend
**Scope:** Large (~12 new files, ~4 modified files)

**Creates:**
| File | Purpose |
|------|---------|
| `components/post/CoAuthorManager.vue` | Manage co-authors (search, invite, remove) |
| `components/post/CoAuthorBadges.vue` | Compact inline display for post cards |
| `components/post/CitationSearchDialog.vue` | Search posts for citation insertion |
| `views/qa/QAListView.vue` | Question listing (badges, answer/vote counts) |
| `views/qa/QACreateView.vue` | Ask question form (reuses TipTap) |
| `views/qa/QADetailView.vue` | Question + answers (best answer pinned, votes) |
| `components/qa/QACard.vue` | Question card for listing |
| `components/qa/VoteButtons.vue` | Vertical up/down arrows with score |
| `components/qa/BestAnswerBadge.vue` | Green checkmark badge |

**Modifies:**
| File | Change |
|------|--------|
| `components/PostCard.vue` | Co-author badges, citation count icon, Q&A link for `type=question` |
| `views/forum/PostDetailView.vue` | Co-author section, citation sections ("Cited by N", "References") |
| `composables/usePostDetail.ts` | Add `isCoAuthor`, update `canModify` logic |
| `views/forum/ForumView.vue` | Pass `type: 'post'` to exclude questions |

**Does NOT modify:** `AppNavbar.vue`, `router/index.ts`, `TiptapEditor.vue` toolbar (citation button deferred to Phase 5 or added here if TiptapEditor is not shared)

**Audit fixes:**
- M-35: `canModify` includes co-author check
- M-38: VoteButtons toggle state management (track current vote per comment)
- M-39: ForumView type filter synchronized with backend
- M-40: Hide vote UI on regular post comments (only show when `post.type === 'question'`)

---

### Phase 4 Verification

```bash
cd frontend && npx tsc --noEmit    # type check
cd frontend && npx vitest run      # all tests pass
cd frontend && npx vite build      # production build succeeds
```

---

### Phase 5: Frontend Integration (1 Agent)

#### Agent 5 — `frontend-integration`

**Purpose:** Connect all features into shared UI elements that multiple features need.

**Modifies:**
| File | Changes |
|------|---------|
| `components/AppNavbar.vue` | Add nav links: Forms (`/forms`), Albums (`/albums`), Q&A (`/qa`), Friends (`/friends`). Both desktop and mobile menus. |
| `router/index.ts` | Add ALL new routes (see below) |
| `views/ProfileView.vue` | Add tabs/links: Invitations (co-author), Friends, Following, Blocked |
| `views/UserProfileView.vue` | Add: SocialActions component, Co-Authored Posts tab, profile view counts, FriendRecommendations (own profile only), hide content for blocked users |
| `components/TiptapEditor.vue` | Add "Cite" toolbar button → opens CitationSearchDialog |
| 17 locale files in `src/locales/` | Add ~200+ new i18n keys for all features |

**New routes to add:**
```typescript
// F1 - Forms
{ path: '/forms', name: 'forms', component: FormsDirectoryView }
{ path: '/forms/new', name: 'standalone-form-create', component: FormBuilderView, meta: { requiresAuth: true, requiresMember: true } }

// F2 - Albums
{ path: '/albums', name: 'albums', component: AlbumsDirectoryView, meta: { requiresAuth: true } }
{ path: '/albums/:id', component: AlbumLayout, meta: { requiresAuth: true, fullWidth: true }, children: [
    { path: '', redirect: 'photos' },
    { path: 'photos', name: 'album-photos', component: AlbumPhotosView },
    { path: 'members', name: 'album-members', component: AlbumMembersView },
    { path: 'comments', name: 'album-comments', component: AlbumCommentsView },
]}
{ path: '/albums/create', name: 'album-create', component: AlbumCreateView, meta: { requiresAuth: true, requiresAdmin: true } }

// F3 - Co-author invitations (under profile)
// (handled within ProfileView tabs, no new route)

// F4 - Social
{ path: '/friends', name: 'friends', component: FriendsView, meta: { requiresAuth: true, requiresMember: true } }
{ path: '/following', name: 'following', component: FollowingView, meta: { requiresAuth: true, requiresMember: true } }
{ path: '/blocked-users', name: 'blocked-users', component: BlockedUsersView, meta: { requiresAuth: true, requiresMember: true } }

// F7 - Q&A
{ path: '/qa', name: 'qa', component: QAListView, meta: { requiresAuth: true, fullWidth: true } }
{ path: '/qa/ask', name: 'qa-ask', component: QACreateView, meta: { requiresAuth: true, requiresMember: true } }
{ path: '/qa/:id', name: 'qa-detail', component: QADetailView, meta: { requiresAuth: true } }
```

**Route ordering rules:**
- `/forms` and `/forms/new` BEFORE `/forms/:formId`
- `/albums/create` BEFORE `/albums/:id`
- `/qa/ask` BEFORE `/qa/:id`

**Audit fixes:**
- M-26: Mobile nav menu updated for all features
- M-28: Loading/error/empty states on all new views (verify)
- M-29: Breadcrumbs on all new views
- M-44: i18n keys for all 17 locales
- M-45: Mobile menu `max-height` adjustment if needed

---

### Phase 5 Verification

```bash
cd frontend && npx tsc --noEmit
cd frontend && npx vitest run
cd frontend && npx vite build
cd frontend && npx prettier --check "src/**/*.{ts,vue}"
```

**Full frontend is now complete. Commit checkpoint.**

---

### Phase 6: Quality Assurance (2 Parallel Agents)

#### Agent 6A — `backend-qa`

**Focus:** Comprehensive backend testing

**Test categories:**
- Edge cases: concurrent friend requests, vote race conditions, citation self-reference
- Blacklist filtering: verify EVERY filtered query returns correct results
- GDPR: `anonymize_user()` cleans up ALL 13 new tables + Redis cache
- Rate limits: all new endpoints respect limits
- Permissions: IDOR checks, admin vs member vs guest access
- Counter reconciliation: run task, verify counters match source-of-truth queries
- Block cascade: unfriend+unfollow+Redis in single transaction

**Files to create:** Additional test files as needed

---

#### Agent 6B — `frontend-qa`

**Focus:** Comprehensive frontend testing

**Test categories:**
- New view component tests (FormsDirectory, Albums, QA, Social, Recommendations)
- PostCard with co-author badges, citation count, Q&A routing
- VoteButtons toggle state
- SocialActions button states (friend/follow/block lifecycle)
- PhotoLightbox keyboard navigation (Escape, Arrow keys)
- Route guards (member-only, admin-only routes)
- Mobile responsiveness
- i18n key completeness check

**Files to create:** Test files in `src/**/__tests__/` or `src/**/*.spec.ts`

---

### Phase 6 Verification

```bash
# Full test suite
cd backend && pytest tests/ -v
cd frontend && npx vitest run

# Lint + type check
cd backend && isort app/ tests/ --check && mypy app/
cd frontend && npx tsc --noEmit && npx prettier --check "src/**/*.{ts,vue}"

# Build
cd frontend && npx vite build
```

---

## 4. Dependency Graph (Visual)

```
Phase 0: [Foundation] ─────────────────────────────────────────────────────────────
              │
              ├──────────────┬──────────────┬──────────────┐
              ▼              ▼              ▼              ▼
Phase 1:  [1A: F1]     [1B: F2]     [1C: F4core]    [1D: F6]
          (Forms)      (Albums)     (Social)        (Recs)
              │              │              │              │
              └──────────────┴──────────────┴──────────────┘
                                    │
                                    ▼
Phase 2:              [2: F3 + F5 + F7]
                      (CoAuth+Views+QA)
                                    │
                                    ▼
Phase 3:              [3: Blacklist Integration]
                                    │
              ┌──────────────┬──────┴─────────┐
              ▼              ▼                 ▼
Phase 4:  [4A: F1+F2]  [4B: F4+F6]     [4C: F3+F5+F7]
          (frontend)   (frontend)       (frontend)
              │              │                 │
              └──────────────┴─────────────────┘
                                    │
                                    ▼
Phase 5:              [5: Frontend Integration]
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
Phase 6:          [6A: Backend QA]    [6B: Frontend QA]
```

---

## 5. Risk Mitigation

### 5.1 Phase 2 Context Window Risk

Phase 2 (F3+F5+F7 in single agent) is the largest agent. If context limit is a concern, split into 3 sequential sub-invocations:
1. Agent 2a: F7 (Q&A) — modifies `services/post.py` first (largest change)
2. Agent 2b: F5 (Views/Citations) — modifies `services/post.py` second
3. Agent 2c: F3 (Co-Authors) — modifies `services/post.py` last

### 5.2 Phase 3 Blast Radius

Blacklist integration touches 15+ existing files. Mitigation:
- Run full test suite after EACH file modification
- Test each filtered query independently
- Admin endpoints must bypass filtering

### 5.3 Migration Rollback

Test `alembic downgrade` for each migration. Downgrade order is reverse of upgrade. Feature 1's downgrade deletes standalone forms (data loss) — document this.

### 5.4 Frontend Build Breaks

Common Vite prod build failure: multiline inline `@click` handlers. All new Vue components must extract complex handlers to named methods.

### 5.5 Merge Point Failures

After each phase, if tests fail:
1. Identify which agent's changes caused the failure
2. Fix in a targeted follow-up agent invocation
3. Do NOT proceed to next phase until tests pass

---

## 6. Estimated Scope per Agent

| Agent | New Files | Modified Files | New Tests | Complexity |
|-------|-----------|----------------|-----------|------------|
| 0 Foundation | ~25 | ~9 | 0 | Medium |
| 1A Forms BE | 0 | 5 | ~14 | Low |
| 1B Albums BE | 5 | 1 | ~25 | High |
| 1C Social BE | 5 | 1 | ~28 | High |
| 1D Recs BE | 4 | 0 | ~10 | Medium |
| 2 Post-Ext BE | 12 | 5 | ~63 | **Very High** |
| 3 Blacklist | 0 | 15+ | ~15 | High |
| 4A Forms+Albums FE | 12 | 5 | ~8 | High |
| 4B Social+Recs FE | 7 | 1 | ~5 | Medium |
| 4C Post-Ext FE | 9 | 4 | ~8 | High |
| 5 FE Integration | 0 | ~22 | ~5 | Medium |
| 6A Backend QA | ~5 | 0 | ~40 | Medium |
| 6B Frontend QA | ~8 | 0 | ~30 | Medium |
| **Total** | **~92** | **~68** | **~241** | |

---

## 7. Commit Strategy

One git commit per phase completion:

```
Phase 0: "feat: add foundation infrastructure for 7 new features"
Phase 1: "feat: implement Forms, Albums, Social core, and Recommendations backends"
Phase 2: "feat: implement Co-Authors, Views/Citations, and Q&A backends"
Phase 3: "feat: integrate blacklist filtering across all content queries"
Phase 4: "feat: implement frontend for all 7 features"
Phase 5: "feat: integrate all features into navigation, routing, and i18n"
Phase 6: "test: comprehensive QA for all 7 features"
```

---

## 8. Quick Reference: Agent Launch Order

```
# Phase 0 (sequential)
Agent 0: foundation

# Phase 1 (4 parallel) — launch together
Agent 1A: forms-backend
Agent 1B: albums-backend
Agent 1C: social-core-backend
Agent 1D: recommendations-backend

# Phase 2 (sequential, after Phase 1 verified)
Agent 2: post-extensions-backend

# Phase 3 (sequential, after Phase 2 verified)
Agent 3: blacklist-integration

# Phase 4 (3 parallel) — launch together
Agent 4A: forms-albums-frontend
Agent 4B: social-recs-frontend
Agent 4C: post-extensions-frontend

# Phase 5 (sequential, after Phase 4 verified)
Agent 5: frontend-integration

# Phase 6 (2 parallel) — launch together
Agent 6A: backend-qa
Agent 6B: frontend-qa
```
