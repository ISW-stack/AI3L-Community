# User Guide Security Audit

**Date:** 2026-03-22
**Scope:** `frontend/src/views/guide/UserGuideView.vue` + all 4 guide content components
**Method:** Static code analysis + 4 parallel automated agents (auth store, build chunks, backend coverage, content inventory)

---

## Executive Summary

The User Guide feature has **6 confirmed security vulnerabilities** ranging from High to Medium severity. The core architectural issue is that guide content is entirely frontend-bundled static HTML with no backend authorization layer, while the client-side access controls are trivially bypassable. In addition, the guide content itself discloses sensitive internal architecture and security mechanism details that enable attacker reconnaissance.

**Backend APIs remain protected** — the backend validates session tokens server-side and rejects unauthorized requests regardless of client-side role manipulation. However, the information disclosed in the guide content can substantially assist targeted attacks.

---

## Vulnerability Summary

| ID | Title | Severity | Exploitability |
|----|-------|----------|----------------|
| G-01 | Route missing role restriction | High | Trivial |
| G-02 | Client-side role stored in localStorage | High | Trivial (1 line of JS) |
| G-03 | Admin/SA guide JS chunks publicly downloadable | High | Easy (direct HTTP GET) |
| G-04 | Guide components have no internal auth checks | Medium | Requires G-02 |
| G-05 | No backend authorization layer | Medium | Architectural |
| G-06 | Sensitive information disclosure in guide content | Medium | Requires G-03 |

---

## Detailed Findings

---

### G-01 — Route Missing Role Restriction

**Severity:** High
**File:** `frontend/src/router/index.ts:302-306`

```ts
{
  path: '/guide',
  name: 'guide',
  component: () => import('@/views/guide/UserGuideView.vue'),
  meta: { requiresAuth: true },  // missing requiresMember: true
},
```

**Issue:** The `/guide` route only requires `requiresAuth: true`. Guest users are authenticated (they hold a valid session with `role: 'GUEST'`), so the router guard does not block them. Compare with the `/about` route which has identical sensitivity but correctly sets `requiresMember: true`.

**Router guard logic** (`router/index.ts:315-346`):
```ts
if (to.meta.requiresAuth && !auth.isAuthenticated) { return { name: 'login' } }
if (to.meta.requiresMember && auth.isGuest) { return { name: 'home' } }
// No check for /guide beyond requiresAuth
```

**Impact:** Any user who obtains an invite code can enter as a Guest and freely access `/guide`, including (after exploiting G-02) the Admin and Super Admin guide tabs.

**Fix:**
```ts
meta: { requiresAuth: true, requiresMember: true },
```

---

### G-02 — Client-Side Role Stored in Plain localStorage

**Severity:** High
**File:** `frontend/src/stores/auth.ts:19-20, 36-44`

```ts
// Role is non-sensitive — kept in localStorage for UI state across page reloads
const role = ref<string | null>(localStorage.getItem('role'))

function setSession(newRole: string, expiresIn: number) {
  role.value = newRole
  localStorage.setItem('role', newRole)
  // ...
}
```

**Issue:** `auth.role` is initialized directly from `localStorage` on every page load. All role-based computed properties (`isAdmin`, `isSuperAdmin`, `isGuest`) are pure client-side string comparisons against this value.

The tab visibility in `UserGuideView.vue` is entirely derived from these computed properties:
```ts
const userRoleLevel = computed(() => ROLE_LEVELS[auth.role || 'GUEST'] ?? 0)
const visibleTabs = computed(() =>
  allTabs.filter((tab) => ROLE_LEVELS[tab.minRole] <= userRoleLevel.value),
)
```

**Exploit (browser console, 2 steps):**
```js
localStorage.setItem('role', 'SUPER_ADMIN')
location.reload()
```

After reload, `userRoleLevel` becomes 3, all 4 guide tabs become visible, and `AdminGuideContent` / `SuperAdminGuideContent` render without any further checks.

**Note:** `fetchProfile()` (`auth.ts:139-157`) syncs the true role from the server, but it returns early for Guest users (`if (role.value === 'GUEST') return`) and is not called on the Guide page. The manipulated role persists for the duration of the Guide session.

**Additional bypass vector — Vue DevTools:**
```
Vue DevTools -> Stores -> auth -> role -> (set to 'SUPER_ADMIN')
```

**Impact:** Any authenticated user (including Guests) can view all Admin and Super Admin guide content through UI manipulation. Combined with G-03, this is not even necessary — but it also allows bypassing `/admin` route guards in the SPA.

**Fix:** Add `requiresMember: true` on the route (G-01 fix) as the primary control. For defense-in-depth, add component-level guards (G-04 fix).

---

### G-03 — Admin/SA Guide JS Chunks Publicly Downloadable

**Severity:** High
**Files:** `nginx/conf.d/default.conf:101-108`, Vite build output

**Confirmed chunk files in `frontend/dist/assets/`:**
```
AdminGuideContent-DFB1TARA.js
SuperAdminGuideContent-BYtWmJQh.js
```

**nginx configuration:**
```nginx
location /assets/ {
    root /usr/share/nginx/html;
    expires 1y;
    add_header Cache-Control "public, immutable";
    access_log off;
    # No auth check
}
```

**Issue:** `defineAsyncComponent()` causes Vite to emit each lazy-loaded component as a separate hashed JS chunk. The nginx `/assets/` location serves these files statically with no authentication check. Since the chunks contain the full rendered template text (not minified to unreadability), their content is directly accessible.

**Chunk discovery methods:**
1. Log in as Guest → open DevTools Network tab → load `/guide` → observe JS chunk requests
2. Inspect Vite manifest (`dist/.vite/manifest.json`) which lists all chunk filenames
3. Inspect `<link rel="modulepreload">` tags in `index.html`

**Exploit:**
```
GET /assets/SuperAdminGuideContent-BYtWmJQh.js
HTTP/1.1 200 OK
Cache-Control: public, immutable
```
No credentials required. Anyone — including unauthenticated users — can download and read the full Super Admin guide content.

**Impact:** G-01, G-02, and session manipulation are all unnecessary. The full Admin and Super Admin guide text is publicly accessible via direct HTTP request.

**Fix options (in order of preference):**
1. **Architectural:** Move guide content to a backend endpoint (`GET /api/v1/guide/{section}`) that validates the session and returns only content appropriate for the caller's role.
2. **Build:** Remove `defineAsyncComponent` for guide content — inline all guide components into the main bundle. This eliminates separate chunks, though the content remains in the bundle (harder to extract, not eliminated).
3. **Nginx:** Proxy `/assets/` through an auth-checking middleware before serving. This is complex and conflicts with the `immutable` caching strategy.

---

### G-04 — Guide Components Have No Internal Auth Checks

**Severity:** Medium
**Files:** `frontend/src/components/guide/AdminGuideContent.vue`, `frontend/src/components/guide/SuperAdminGuideContent.vue`

**Verified content of `AdminGuideContent.vue` `<script setup>`:**
```ts
import BaseAlert from '@/components/base/BaseAlert.vue'
// No auth store import, no role checks
```

**Verified content of `SuperAdminGuideContent.vue` `<script setup>`:**
```ts
import BaseAlert from '@/components/base/BaseAlert.vue'
// No auth store import, no role checks
```

Both components are pure presentational HTML. They render their full content unconditionally if the parent renders them. There is no `v-if` guard, no `useAuthStore()` injection, no role validation.

**Issue:** Defense-in-depth is absent. The only access control is the parent `UserGuideView.vue`'s `v-if` conditionals on `activeTab`, which are themselves bypassable via G-02.

**Fix:**
```ts
// AdminGuideContent.vue
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
// In template: wrap root element with v-if="auth.isAdmin"

// SuperAdminGuideContent.vue
const auth = useAuthStore()
// In template: wrap root element with v-if="auth.isSuperAdmin"
```

Note: This is defense-in-depth only. The root fix for the chunk exposure (G-03) requires architectural changes.

---

### G-05 — No Backend Authorization Layer

**Severity:** Medium (Architectural)
**Confirmed by:** Backend search across `app/api/v1/endpoints/`, `app/services/`, `app/repositories/`

**Findings:**
- Zero backend files related to guide content
- Zero API calls in any guide component (`grep` confirms no `import ... from '@/api'` in guide files)
- Guide content is hardcoded static HTML in Vue SFC templates
- All access control is client-side only

**Issue:** If an attacker bypasses the client-side controls (trivial, as shown in G-01–G-03), there is no server-side fallback. The system cannot distinguish between a legitimate Super Admin reading the guide and a Guest who manipulated their localStorage role.

**Impact:** The entire authorization model for the Guide feature is client-side, making it non-enforceable.

---

### G-06 — Sensitive Information Disclosure in Guide Content

**Severity:** Medium
**Applicable after:** G-03 (no login required to read chunks)

#### High-Sensitivity Disclosures

| Disclosed Information | Source | Attack Use |
|-----------------------|--------|------------|
| `GET /health` endpoint path | SuperAdmin Guide | API endpoint enumeration |
| `/health` returns: DB pool size/free/in-use, Redis status, MinIO status, Celery status | SuperAdmin Guide | Internal infrastructure mapping |
| `GET /health/live` is public | SuperAdmin Guide | Unauthenticated health probing |
| Audit log records: role changes, bans, deletions, application reviews, IP bans, invite codes, SIG operations | SuperAdmin Guide | Identify unlogged operations for stealthy attacks |
| IP ban supports IPv4 + IPv6, permanent bans possible, delete = immediate unblock | SuperAdmin Guide | IP rotation bypass strategy |
| Password policy: 8+ chars, uppercase, lowercase, digit, special character | Guest Guide | Dictionary/brute-force optimization |
| Only Super Admins can create Admin accounts | Admin Guide | Privilege escalation path mapping |
| Cannot delete Super Admin accounts, cannot ban self, cannot change own role | SuperAdmin Guide | Understand system constraints for bypass design |

#### Medium-Sensitivity Disclosures

| Disclosed Information | Source | Attack Use |
|-----------------------|--------|------------|
| Draft auto-saved per-SIG + per-user | Member Guide | Draft key format inference |
| DM: 50K char cap, oldest messages auto-deleted when exceeded | Member Guide | Message retention behavior |
| DM: file attachments deleted after 3 days, text after 30 days | Member Guide | Evidence destruction timing window |
| DM: 12-hour edit/recall window | Member Guide | Social engineering timing |
| Password change causes auto-logout after 1.5 seconds | Member Guide | Session management behavior prediction |
| File upload: 50MB per file, 1GB per user quota | Member Guide | Storage exhaustion DoS vector |
| VirusTotal scan returns 202 while pending | Member Guide | Upload scanning bypass via timing window |
| Form max_respondents limit exists | Member Guide | Race condition attack target |
| Invite code statuses: Active, Used, Revoked | Admin Guide | Invite code lifecycle tracking |
| Sub-Admin can demote members "below own level" | Member Guide | Role comparison logic exploitable |
| Platform Admins automatically have SIG Admin-level access to all SIGs | Admin Guide | Lateral movement path via SIG takeover |

#### Low-Sensitivity Disclosures

| Disclosed Information | Source |
|-----------------------|--------|
| Guest sessions are server-side, expire on inactivity | Guest Guide |
| Guest limitation list (implies which API endpoints require auth) | Guest Guide |
| Post edit history is queryable, each edit creates a new version | Member Guide |
| Co-author invitations stored in Profile > Social tab | Member Guide |
| Org chart hidden entries visible only to Super Admins | SuperAdmin Guide |
| GitHub usernames stored in backend, proxied in frontend | SuperAdmin Guide |

---

## Attack Chain Demonstration

The following chain requires no special access beyond obtaining a single invite code:

```
Step 1: Obtain invite code (social engineering or leaked code)
         |
Step 2: Guest Login -> access /guide (G-01: route allows it)
         |
Step 3: Directly download chunk (G-03: no auth required):
         GET /assets/SuperAdminGuideContent-BYtWmJQh.js -> HTTP 200
         |
Step 4: Read full Admin + Super Admin guide content (G-06):
         - Learn GET /health exists and what it returns
         - Learn audit log scope (identify blind spots)
         - Learn IP ban mechanism (plan IP rotation)
         - Learn privilege escalation path (Guest -> Member -> Admin requires SA)
         |
Step 5: Use reconnaissance data to plan targeted attack
```

The backend correctly rejects unauthorized API calls regardless of client-side manipulation — but **reconnaissance itself is the threat**. The information gathered enables significantly more effective targeted attacks.

---

## Risk Matrix

| Vulnerability | Likelihood | Impact | Overall |
|---------------|------------|--------|---------|
| G-01: Route missing guard | High (trivial access) | Medium | **High** |
| G-02: localStorage role tampering | High (trivial exploit) | Medium | **High** |
| G-03: Public chunk download | High (no auth needed) | Medium | **High** |
| G-04: No component guards | Medium (needs G-02) | Low | **Medium** |
| G-05: No backend layer | High (architectural) | Medium | **High** |
| G-06: Info disclosure | High (via G-03) | Medium | **High** |

---

## Remediation Plan

### P0 — Immediate (1-2 hours)

**Fix G-01:** Add `requiresMember: true` to the guide route.

```ts
// frontend/src/router/index.ts
{
  path: '/guide',
  name: 'guide',
  component: () => import('@/views/guide/UserGuideView.vue'),
  meta: { requiresAuth: true, requiresMember: true },
},
```

**Fix G-04:** Add role guards inside Admin and Super Admin guide components.

```ts
// AdminGuideContent.vue — add to <script setup>
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
// Wrap template root with: v-if="auth.isAdmin"

// SuperAdminGuideContent.vue — add to <script setup>
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
// Wrap template root with: v-if="auth.isSuperAdmin"
```

### P1 — Short-term (1-3 days)

**Fix G-06 (partial):** Remove high-sensitivity internal details from guide content:
- `SuperAdminGuideContent.vue`: Remove explicit `GET /health` endpoint path; replace infrastructure list (DB pool, Redis, MinIO, Celery) with generic "system diagnostics"
- `SuperAdminGuideContent.vue`: Replace specific audit log event list with "All significant administrative actions are recorded"
- `GuestGuideContent.vue`: Remove explicit password policy rules (the registration form validates inline — the guide does not need to specify the exact requirements)

### P2 — Long-term (architectural)

**Fix G-03 + G-05 (root cause):** Move guide content to a backend-served endpoint.

```
GET /api/v1/guide/{section}
Authorization: Session cookie (validated server-side)
Response: Returns guide HTML/JSON only for sections the caller's role permits
```

This eliminates the JS chunk exposure entirely — no guide content is bundled in the frontend.

**Alternative if backend endpoint is not feasible:** Remove `defineAsyncComponent` from guide imports. Inlining all guide content into the main bundle does not eliminate disclosure (the content still exists in the bundle), but removes the trivially discoverable separate chunk files.

---

## Files Affected

| File | Issue |
|------|-------|
| `frontend/src/router/index.ts:302-306` | G-01: Missing `requiresMember` |
| `frontend/src/stores/auth.ts:19-20` | G-02: Role in localStorage |
| `frontend/src/views/guide/UserGuideView.vue:6-17, 27-44` | G-02, G-04: Client-side tab control |
| `frontend/src/components/guide/AdminGuideContent.vue` | G-04, G-06: No guard, sensitive content |
| `frontend/src/components/guide/SuperAdminGuideContent.vue` | G-04, G-06: No guard, sensitive content |
| `frontend/src/components/guide/GuestGuideContent.vue` | G-06: Password policy disclosure |
| `frontend/src/components/guide/MemberGuideContent.vue` | G-06: DM/file/form implementation details |
| `nginx/conf.d/default.conf:101-108` | G-03: Unauthenticated asset serving |

---

*Generated by security audit on 2026-03-22. All findings verified by automated code analysis agents.*
