# Backend Systemic Bug Analysis Report

This document outlines the findings of a detailed, systemic analysis of the AI3L-Community backend, focusing on easily overlooked bugs, concurrency issues, architectural flaws, and scalability bottlenecks.

## 1. Concurrency: Invite Code Race Condition (Registration Flow)
**Location:** `app/api/v1/endpoints/auth.py` (`register` endpoint) and `app/services/auth.py` (`register_new_user`).

**Description:**
The registration flow validates the invite code first using `get_invite_code(req.invite_code)`. Later, it proceeds to register the user by calling `register_new_user`, which executes a raw transaction:
```sql
INSERT INTO users (...) VALUES (...)
UPDATE invite_codes SET consumed_at = NOW(), consumed_by = $1 WHERE code = $2
```
Between the read validation (`get_invite_code`) and the write transaction (`UPDATE invite_codes`), there is a window of time where another concurrent request can use the exact same invite code. Because the `UPDATE` query does not explicitly verify `consumed_at IS NULL`, both concurrent requests will succeed and the single invite code will be reused by multiple accounts.

**Remediation:**
Modify the `UPDATE` statement in `register_new_user` to include `AND consumed_at IS NULL`. Check the number of affected rows; if it's `0`, the invite code was already consumed and the transaction should be aborted. Do not rely solely on the initial `get_invite_code` check.

---

## 2. Architectural Flaw: Editor File Permissions (Broken Images)
**Location:** `app/api/v1/endpoints/files.py` (`upload_editor_file` and `get_presigned_url`).

**Description:**
When a user uploads a file for the rich text editor (e.g., an image to be embedded in a post), the backend returns a 7-day presigned URL. This URL is presumably embedded directly into the post's HTML content.
However, in `get_presigned_url`, access is strictly controlled:
```python
owns_file = key.startswith(f"editor/{current_user['sub']}/") ...
if not is_admin and not owns_file:
    raise HTTPException(status_code=403, detail="You do not have permission...")
```
After 7 days, the embedded presigned URL will expire. When a reader opens the post, the images will fail to load. If the frontend attempts to fetch a new presigned URL for those images using the file key, the backend will return a `403 Forbidden` because the reader is not the original owner (`owns_file` is `False`). This means all embedded images will permanently break for the audience after 7 days.

**Remediation:**
Change how `editor` uploaded files are served. Instead of generating temporary presigned URLs, Editor content should ideally be served via a proxy endpoint that verifies if the requesting user has access to the *Post* where the image is embedded, or the files should be made public/read-only if posts are public. Restricting read access of an embedded S3 object strictly to its uploader defeats its purpose in a community forum.

---

## 3. Concurrency: Storage Quota Enforcement Bypass
**Location:** `app/api/v1/endpoints/files.py` (`upload_editor_file`).

**Description:**
Before uploading a file, the endpoint checks if the current storage usage plus the new file size exceeds the strict quota:
```python
used = await get_user_storage_used(current_user["sub"])
if used + len(data) > settings.MAX_USER_STORAGE_BYTES:
    raise HTTPException(...)
```
If a user rapidly fires multiple concurrent upload requests, all of them will read the current `used` value before any of the uploads finish and persist the new storage sizes. Consequently, all requests will pass the `if` check, resulting in the user successfully bursting past the `MAX_USER_STORAGE_BYTES` limit.

**Remediation:**
Use Redis to implement a distributed lock or an atomic increment/decrement counter for the user's storage usage. Increment the expected storage size in Redis *before* passing the file to S3, and revert it if the S3 upload fails.

---

## 4. Scalability Bottleneck: Offset Pagination
**Location:** `app/repositories/post_repo.py` (`find_many` and `search` functions).

**Description:**
For listing and searching posts, the backend relies purely on SQL `OFFSET` pagination:
```sql
... ORDER BY {order_by} LIMIT $idx OFFSET $idx + 1
```
While this works perfectly for small datasets, it degrades significantly in performance as the `OFFSET` value grows. To satisfy `OFFSET 10000`, the PostgreSQL database must scan, retrieve, and then discard the first 10,000 rows before returning the requested rows. In a community application with an eventual high volume of posts or deep searching, this will lead to severe database CPU spikes and slow response times.

**Remediation:**
Migrate to Keyset Pagination (also known as Cursor Pagination). Instead of passing an `offset`, the client passes the timestamp (or unique sort identifier) of the last item they saw, and the backend queries `WHERE created_at < $last_seen ORDER BY created_at DESC LIMIT 20`. This allows the database to instantly jump to the correct index without scanning discarded rows.

## Summary Conclusion
The core backend demonstrates solid security practices in areas such as Redis JWT sessions, XSS HTML sanitization for posts, and atomic Lua rate limits. However, the identified issues highlight the need for atomic locking during registration/file uploads and a redesign of the S3 asset permissions model to ensure community posts remain readable over time.
