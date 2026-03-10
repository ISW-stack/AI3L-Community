# Database Optimization Audit

Date: 2026-03-07

## HIGH Priority

### 1. OFFSET-Based Pagination Anti-Pattern
- **Files:** All repository files in `backend/app/repositories/`
- **Issue:** Every paginated query uses `OFFSET (page-1)*page_size`. For deep pages (e.g., page 500), PostgreSQL must scan and discard `500*20 = 10,000` rows before returning results.
- **Impact:** Query time grows linearly with page number. On tables with 100k+ rows, deep pagination causes timeouts.
- **Fix:** Implement cursor-based (keyset) pagination using `WHERE id < $last_seen_id ORDER BY id DESC LIMIT $page_size`. Requires API changes to accept cursor instead of page number.

### 2. Missing Database Indexes
- **Locations:** Various tables
- **Issues identified:**
  - `posts.sig_id` — no index; SIG posts listing does full table scan
  - `posts.category_id` — no index; category filtering scans all posts
  - `posts.author_id` — no index; user profile post listing is slow
  - `comments.post_id` — may lack index; comment loading for posts is O(n)
  - `form_responses.form_id` — no index; response listing scans all responses
  - `notifications.user_id + is_read` — composite index needed for unread count queries
- **Fix:** Add targeted B-tree indexes on foreign key columns used in WHERE/JOIN clauses.

### 3. N+1 Query in Comment Tree Building
- **File:** `backend/app/repositories/comment_repo.py`
- **Issue:** Comment tree building may fetch child comments in a loop (one query per parent comment) rather than fetching all comments for a post in a single query and building the tree in memory.
- **Fix:** Single query `WHERE post_id = $1` + in-memory tree construction using a dict keyed by parent_id.

## MEDIUM Priority

### 4. `COUNT(*) OVER()` on Large Tables
- **Files:** All repository `find_many` functions
- **Issue:** While `COUNT(*) OVER()` avoids a second query, it still computes the total count for every row in the result set. On tables with complex WHERE clauses and 100k+ rows, this adds significant overhead.
- **Fix:** Consider caching total counts or using estimated counts (`reltuples` from `pg_class`) for non-critical UI elements. Exact count only when needed.

### 5. Expensive Subquery in `form_repo.py` Response Count
- **File:** `backend/app/repositories/form_repo.py:143-159`
- **Issue:** Form listing includes a correlated subquery `(SELECT COUNT(*) FROM form_responses WHERE form_id = f.id)` for each form. With many forms and responses, this becomes O(n*m).
- **Fix:** Use a LEFT JOIN with GROUP BY, or cache response counts in the forms table.

### 6. Full Table Scan for Full-Text Search
- **File:** `backend/app/repositories/post_repo.py`
- **Issue:** FTS queries using `websearch_to_tsquery` may not use a GIN index if one hasn't been created on the `tsvector` column.
- **Fix:** Verify GIN index exists on the search vector column. Create one if missing: `CREATE INDEX idx_posts_fts ON posts USING gin(search_vector)`.

## LOW Priority

### 7. No Connection Pooling Monitoring
- **Issue:** asyncpg pool is configured with min=10, max=30 but there's no monitoring of pool exhaustion or wait times.
- **Fix:** Add pool stats to the health endpoint or metrics system.

### 8. Transaction Isolation Concerns
- **Issue:** Most repository operations use default READ COMMITTED isolation. For operations that require consistency (like bulk operations), this may lead to phantom reads.
- **Fix:** Use SERIALIZABLE or REPEATABLE READ for critical multi-step operations.
