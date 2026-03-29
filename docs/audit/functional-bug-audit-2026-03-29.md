# Functional Bug Audit — 2026-03-29

> **Methodology**: 7 parallel agents analyzed ~540 source files across auth, posts/comments/SIG, forms/files, DM/notifications/WebSocket, admin/user management, frontend state/UX, and data integrity/SQL. ~70 raw findings were then verified by reading source code. False positives are listed at the end for transparency.

---

## CRITICAL (1)

### C-01: ADMIN role post deletion treated as non-admin

- **File**: `backend/app/api/v1/endpoints/posts.py:296`
- **Roles affected**: ADMIN

```python
is_admin = current_user["role"] == "SUPER_ADMIN"  # BUG: misses "ADMIN"
```

The endpoint allows both `SUPER_ADMIN` and `ADMIN` (line 294), but `is_admin` is only `True` for `SUPER_ADMIN`. Consequences:

1. `soft_delete_post()` runs with `is_admin=False`, taking the `WHERE user_id = $2` path (line 368-373) — **ADMIN cannot delete other users' posts**
2. Audit log records `USER_DELETE_POST` instead of `ADMIN_DELETE_POST` (line 303)

**Fix**: `is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")`

---

## HIGH (5)

### H-01: Guest form submissions bypass all file validation

- **File**: `backend/app/services/form.py:569`
- **Roles affected**: GUEST

```python
if not is_guest:
    _validate_file_ownership(questions, answers, user_id)
    await _validate_file_scan_status(questions, answers)
    await _validate_file_sizes(questions, answers)
```

When a form contains `file_upload` questions and allows guest responses, guest-submitted files skip VirusTotal scan status checks, size validation, and ownership verification.

**Impact**: Guests can submit malicious or oversized files through form responses.

---

### H-02: Form file uploads lack magic byte validation

- **File**: `backend/app/services/form.py:651-658`
- **Roles affected**: MEMBER, ADMIN

Form `file_upload` answer validation only checks file extensions via `.rsplit(".", 1)`, unlike editor file uploads which call `validate_magic_number()` (in `file_validation.py:298`). An attacker can rename an executable to `.pdf` and upload it.

**Fix**: Call `validate_magic_number()` for form file uploads, same as editor uploads.

---

### H-03: DM admin audit event silently swallowed

- **File**: `backend/app/api/v1/endpoints/dm.py:98-99`
- **Roles affected**: SUPER_ADMIN

```python
except Exception:
    pass  # best-effort audit
```

When a SUPER_ADMIN views DM conversations for moderation, the audit log write failure is completely silent — no log, no retry, no fallback. This is a security-sensitive operation that should always be recorded.

**Fix**: Replace `pass` with `logger.error("Failed to log DM admin access", exc_info=True)`.

---

### H-04: SIG member removal uses hard DELETE, inconsistent with soft-delete model

- **File**: `backend/app/repositories/sig_repo.py:188`
- **Roles affected**: ADMIN, SIG_ADMIN

```python
# remove_member() at line 188 — hard delete
"DELETE FROM sig_members WHERE sig_id = $1 AND user_id = $2 AND is_deleted = false"

# soft_delete() at line 176 — soft delete
"UPDATE sig_members SET is_deleted = true WHERE sig_id = $1"
```

When a SIG is soft-deleted, members are marked `is_deleted = true` (restorable). But when a member is individually removed via `remove_member()`, the row is permanently deleted. If the SIG is later restored, these members are lost.

**Fix**: Change `remove_member()` to use `UPDATE sig_members SET is_deleted = true` instead of `DELETE`.

---

### H-05: Bulk role change audit log lacks per-user detail

- **File**: `backend/app/api/v1/endpoints/users.py:342`
- **Roles affected**: SUPER_ADMIN

```python
target_id=f"role={req.role},count={count}"
```

Only records the target role and count, not which specific users were changed. The `changed_ids` list is available (line 326) but never written to the audit log. Post-incident investigation cannot determine which accounts were affected.

**Fix**: Log `changed_ids` in the audit metadata or emit per-user audit entries.

---

## MEDIUM (8)

### M-01: Comment pagination not reset on post change

- **File**: `frontend/src/composables/usePostDetail.ts:715-743`
- **Roles affected**: MEMBER (reading posts)

The `watch(postId, ...)` handler resets `comments.value = []` (line 715) but does not call `setCommentPage(1)`. If a user was on comment page 3 for post A and navigates to post B, `fetchComments()` (line 743) still uses `commentPage.value = 3`, fetching the wrong page.

**Fix**: Add `setCommentPage(1)` in the postId watcher alongside the comment reset.

---

### M-02: DM unread count drifts with concurrent WebSocket messages

- **File**: `frontend/src/views/DMView.vue:144-147`
- **Roles affected**: MEMBER (DM)

```typescript
const prevUnread = dmStore.conversations[convIdx].unread_count  // snapshot
await dmApi.markConversationRead(conversationId)                // API call
dmStore.unreadCount = Math.max(0, dmStore.unreadCount - prevUnread) // stale decrement
```

Between the `prevUnread` snapshot and the API response, a WebSocket `NEW_DM` event can increment `unreadCount`. The decrement still uses the stale snapshot value, causing a permanent offset.

**Fix**: After the API call succeeds, fetch the fresh unread count from the server instead of using the stale snapshot.

---

### M-03: Last SUPER_ADMIN protection has TOCTOU race under concurrency

- **File**: `backend/app/services/user.py:591-596`
- **Roles affected**: SUPER_ADMIN

```python
remaining = await user_repo.count_super_admins_excluding(user_ids, conn)
if remaining == 0:
    raise ValueError(...)
count, changed_ids = await user_repo.bulk_update_role(user_ids, role, conn)
```

Under PostgreSQL `READ COMMITTED`, two concurrent bulk demotion transactions can both see `remaining = 1` (the other transaction hasn't committed yet), then both proceed to demote, leaving zero SUPER_ADMINs.

**Fix**: Use `SELECT ... FOR UPDATE` in `count_super_admins_excluding` to serialize concurrent checks.

---

### M-04: Form stats return 0 for unanswered optional rating questions (ambiguous)

- **File**: `backend/app/services/form.py:324-327`
- **Roles affected**: ADMIN (viewing form statistics)

```python
else:
    stats["average"] = 0.0
    stats["min"] = 0
    stats["max"] = 0
```

When a rating question has zero responses (`rating_counts[qid] == 0`), the API returns `min=0, max=0, average=0.0`. The frontend cannot distinguish "nobody answered" from "everyone rated 0".

**Fix**: Return `null` for min/max/average when `rc == 0`, or add a `response_count` field to disambiguate.

---

### M-05: Non-existent SIG returns empty post list instead of 404

- **File**: `backend/app/api/v1/endpoints/sigs.py:281-296`
- **Roles affected**: MEMBER

`get_sig_posts` does not verify SIG existence before querying posts. Passing a non-existent UUID returns `{"posts": [], "total": 0}` instead of a 404 error, inconsistent with other endpoints that validate resource existence first.

**Fix**: Add a SIG existence check before querying posts.

---

### M-06: WebSocket onReconnect callbacks never cleaned up

- **File**: `frontend/src/composables/useWebSocket.ts:73`
- **Roles affected**: All authenticated users

```typescript
_reconnectCallbacks.push(cb)  // push only, no removal mechanism
```

`onReconnect` only pushes to the array with no unregister API. In practice, `App.vue` only mounts once so this is low-impact, but if components calling `onReconnect` are ever re-mounted, callbacks accumulate and fire multiple times.

**Fix**: Return an unsubscribe function from `onReconnect`, or clear the array on `cleanup()`.

---

### M-07: Form submission allows references to deleted files

- **File**: `backend/app/services/form.py:722-741`
- **Roles affected**: MEMBER

`_validate_file_sizes` calls `get_file_size(key)` which returns 0 for non-existent files. The check `if file_size > max_bytes` never triggers for size 0, allowing form submissions that reference deleted files.

**Fix**: Check for `file_size == 0` and reject with "File not found" error.

---

### M-08: Empty PATCH to user preferences silently returns defaults

- **File**: `backend/app/repositories/preferences_repo.py:45-50`
- **Roles affected**: MEMBER

When all preference fields are `None` (empty PATCH body), `upsert_preferences` returns hardcoded defaults instead of fetching and merging with existing preferences. This can silently reset preferences.

**Fix**: Fetch existing preferences first, then merge with non-None fields from the request.

---

## LOW (4)

### L-01: ADMIN post deletion audit logged as USER_DELETE_POST ✅

- **File**: `backend/app/api/v1/endpoints/posts.py:303`
- **Roles affected**: ADMIN

Derivative of C-01. Since `is_admin=False` for ADMIN users, the audit action is `USER_DELETE_POST` instead of `ADMIN_DELETE_POST`. Fixed automatically when C-01 is resolved.

**Status**: Already fixed (C-01 was previously resolved).

---

### L-02: Profile view recording is best-effort only ✅

- **File**: `backend/app/api/v1/endpoints/users.py:455`
- **Roles affected**: All users

Profile view count recording fails silently, meaning view statistics can be inaccurate under load or transient errors. Acceptable for non-critical metrics but worth noting.

**Fix applied**: Replaced silent `pass` with `logger.warning(...)` including `exc_info=True` so failures are visible in logs without breaking the request.

---

### L-03: Rating distribution dict allows out-of-range values ✅

- **File**: `backend/app/services/form.py:272`
- **Roles affected**: ADMIN (viewing statistics)

`rating_dists[qid][value]` stores the count without validating that `value` falls within the question's configured min/max range. Corrupted data in the database could produce unexpected distribution keys.

**Fix applied**: Added range validation (`q_min`/`q_max` from question config) before accumulating rating values. Out-of-range values are logged as warnings and skipped. New test: `test_stats_rating_out_of_range_excluded`.

---

### L-04: About page avatar cache size tracking inaccurate in multi-worker ✅

- **File**: `backend/app/api/v1/endpoints/about.py:152-163`
- **Roles affected**: MEMBER (viewing about page)

`_cache_total_bytes` is a module-level global. In multi-worker deployments (e.g., gunicorn with multiple workers), each process tracks its own cache size independently, potentially exceeding the intended memory limit per-worker.

**Fix applied**: Reduced per-worker limits (5 MB total, 2 MB per avatar, 30 entries) so multi-worker deployments stay within reasonable memory bounds. Added documentation comment explaining the per-worker nature of the cache.

---

## Verified False Positives

The following items were reported by audit agents but confirmed correct after source code verification:

| Finding | Reason for dismissal |
|---------|---------------------|
| DM read receipt `sender_id` inverted | `sender_id=other_id` is correct — notifies the message sender that their messages were read |
| WebSocket `ping_loop` stale `last_pong` variable | Python closures correctly share the enclosing scope variable; asyncio cooperative scheduling prevents races |
| `application_repo` OFFSET/LIMIT reversed | Verified `[offset, limit]` maps to `OFFSET $idx LIMIT $idx+1` — order is correct |
| DM converter `last_msg_sender_avatar_url` not resolved | Line 64 calls `async_resolve_avatar_url` — correctly resolved |
| Notification converter `trigger_avatar_url` not resolved | Lines 19 and 40 call `resolve_avatar_url` — correctly resolved |
| Co-author avatar URL not resolved | `co_author_converter.py:10` calls `async_resolve_avatar_url` — correctly resolved |
| Router guard missing SIG_ADMIN check | SIG_ADMIN is a per-SIG role, not a platform role; `requiresAdmin` correctly restricts to platform ADMIN+ |
| `searchPage` not reset on filter change | `doSearch()` line 207 sets `searchPage.value = 1` — correctly reset |
| Password change allows same password | Line 551 `if old_password == new_password: raise ValueError` — correctly checked |
| Form stats crash when `rc > 0` but `rating_mins` is `None` | If `rc > 0`, at least one value passed `isinstance(int)`, guaranteeing `rating_mins` was set at line 269 |

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH     | 5 |
| MEDIUM   | 8 |
| LOW      | 4 |
| **Total** | **18** |

### By Role

| Role | Bugs |
|------|------|
| SUPER_ADMIN | H-03, H-05, M-03 |
| ADMIN | C-01, H-02, H-04, M-04, L-01 |
| SIG_ADMIN | H-04 |
| MEMBER | H-02, M-01, M-02, M-05, M-07, M-08, L-02 |
| GUEST | H-01 |

### Recommended Fix Priority

1. **C-01** — one-line fix, blocks ADMIN moderation capability
2. **H-01** — security: unscanned guest file uploads
3. **H-02** — security: file type spoofing in forms
4. **H-03** — one-line fix, silent audit gap
5. **H-04, H-05** — data consistency and audit completeness
6. **M-01 through M-08** — fix per module
