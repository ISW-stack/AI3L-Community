# Database Optimization Audit

Date: 2026-03-07 (updated 2026-03-11)

## HIGH Priority

### 1. OFFSET-Based Pagination Anti-Pattern
- **Files:** All repository files in `backend/app/repositories/`
- **Status:** Still uses OFFSET-based pagination. Mitigated by `COUNT(*) OVER()` pattern. Cursor-based pagination is an architectural improvement for future consideration when tables exceed 100k+ rows.

### 2. Missing Database Indexes — ✅ Resolved
- **Status:** All required indexes exist across migration files: `ix_posts_sig_id`, `ix_posts_category_id`, `ix_posts_user_id`, `ix_comments_post_id`, `ix_form_responses_form_id`, `idx_notifications_user_is_read` (partial index), plus composite indexes for common query patterns.

### 3. N+1 Query in Comment Tree Building — ✅ Resolved
- **Status:** `comment_repo.find_many()` fetches all comments in a single query with `COUNT(*) OVER()`. No loop-based child fetching.

## MEDIUM Priority

### 4. `COUNT(*) OVER()` on Large Tables — ✅ Resolved
- **Status:** Consistently implemented across all repository `find_many` functions with fallback COUNT query for empty result sets.

### 5. Expensive Subquery in `form_repo.py` Response Count — ✅ Resolved
- **Status:** Uses non-correlated `LEFT JOIN (SELECT form_id, COUNT(*) ... GROUP BY form_id)` — optimal single hash aggregate.

### 6. Full Table Scan for Full-Text Search — ✅ Resolved
- **Status:** GIN index `ix_posts_search_vector` exists on `posts.search_vector` column.

## LOW Priority

### 7. No Connection Pooling Monitoring
- **Issue:** asyncpg pool (min=10, max=30) has no monitoring of pool exhaustion or wait times.
- **Fix:** Add pool stats to health endpoint or metrics system.

### 8. Transaction Isolation Concerns
- **Issue:** Most operations use default READ COMMITTED. SERIALIZABLE or REPEATABLE READ may be needed for critical multi-step operations.
- **Fix:** Evaluate on a case-by-case basis for bulk operations.
