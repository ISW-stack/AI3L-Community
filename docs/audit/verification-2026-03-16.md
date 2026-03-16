# Audit Verification Report

> Date: 2026-03-16 | Verifies: system-bugs, security-audit, uiux-audit

---

## Verification Summary

| Report | Total Findings | Confirmed | Partially Confirmed | Rejected | Severity Adjusted |
|--------|---------------|-----------|-------------------|----------|------------------|
| System Bugs (B01-B18) | 15 verified | 9 | 4 | 2 | 7 |
| Security (S01-S23) | 13 verified | 8 | 2 | 3 | 4 |
| UI/UX (U01-U28) | 23 verified | 14 | 2 | 7 | — |

---

## Rejected Findings (False Positives)

### B06: Comment count desync — PARTIALLY CONFIRMED (downgraded to Low)
Backend correctly cascades. Frontend decrements by 1, but re-fetches comments after delete. Temporary UI-only desync until next refresh.

### S04/S05: Album upload size + type validation — REJECTED
Service layer (`album.py`) has `ALBUM_MAX_PHOTO_SIZE_BYTES`, `ALBUM_ALLOWED_IMAGE_TYPES`, and magic number validation. **However**, endpoint reads full file into memory BEFORE service validates → B02 remains valid as memory exhaustion (Medium).

### U02: v-html without DOMPurify in PostDetailView — REJECTED
`usePostDetail.ts:172` calls `DOMPurify.sanitize(post.value.content)` BEFORE segmentation. All v-html usages are already sanitized.

### U28: Arabic locale no RTL — REJECTED
`useLocale.ts:13` sets `document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'`. Basic RTL support exists.

### B13: Login doesn't honor redirect param — REJECTED
`LoginView.vue:46-56` reads `route.query.redirect`, validates origin, and navigates there. Works correctly.

### S07: CSP missing ws: — REJECTED (finding was that ws: IS present)
Both `ws:` and `wss:` already in CSP `connect-src`. The issue is that `ws:` should be REMOVED for production (not missing).

### S23: upgrade-insecure-requests in CSP — REJECTED (already present)
Already present. The concern about dev breakage is valid but minor.

---

## Severity Adjustments

| ID | Original | Adjusted | Reason |
|----|----------|----------|--------|
| B01 | High | Low | By design; single-session is intentional |
| B02 | High | Medium | Service has size check, but full read happens first |
| B03 | High | Low | Design trade-off; blocking pending degrades UX |
| B04 | Medium | Low | TOCTOU window is real but very narrow |
| B05/S03 | Medium/High | Low | Not SQL injection; ILIKE wildcards only, results capped |
| B06 | Medium | Low | Temporary UI desync, backend correct |
| B07 | Medium | Low | Text UUID comparison is actually correct lexicographically |
| B08 | Medium | Low | Edge case requiring content that sanitizes to empty |

---

## Confirmed High/Critical (Still Valid After Verification)

| ID | Severity | Finding |
|----|----------|---------|
| S01 | Critical | Real super admin password in `.env` |
| S02 | Critical | Default JWT secret `changeme_jwt_secret_key` in use |
| S16 | Medium | nginx location blocks silently drop all security headers |
| B11 | Medium | cleanup_orphan_files loads all S3 files into memory |
| B12 | Medium | get_form_stats loads all responses into memory |
| B16 | Medium | Post author not notified of new comments |
| U01 | High | QA "Ask Question" routes to non-existent `/qa/create` |
| U03 | Medium | Missing autocomplete on all auth forms |
| U06 | Medium | `<html lang="zh-TW">` hardcoded (should be `en`) |
| U07 | Medium | No beforeRouteLeave on PostCreateView |
| U08 | Medium | Admin create has no password validation |
| U09 | Medium | Forms search only filters current page |
