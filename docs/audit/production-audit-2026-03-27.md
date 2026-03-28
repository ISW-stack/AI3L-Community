# AI3L Community — 生產環境安全與 Bug 審計報告

**日期：** 2026-03-27
**範圍：** 後端 (FastAPI + asyncpg + Redis + Celery)、前端 (Vue 3 + TypeScript)、基礎設施 (Docker + nginx + PostgreSQL + Redis + MinIO)、業務邏輯
**方法：** 四組平行靜態分析（後端安全、前端安全、基礎設施、業務邏輯）
**修復狀態：** 7 Critical 全部修復 (2026-03-28)，18 新測試全部通過

---

## 摘要

| 嚴重程度 | 數量 |
|---------|------|
| Critical | 7 |
| High | 14 |
| Medium | 25 |
| Low | 16 |
| **合計** | **62** |

---

## CRITICAL — 必須在上線前修復

### C-01: 表單 max_respondents 競態條件（可超額 1 人）

**檔案：** `backend/app/repositories/form_repo.py:408-419`
**說明：** advisory lock 內的 `INSERT...SELECT` 使用 `COUNT(*) < $5` 比對上限，但 COUNT 與 INSERT 並非原子操作。兩個並行請求可在同一瞬間各自讀到 99（上限 100），各自插入，最終 101 筆回覆。
**重現：** 高併發下同時提交表單（ab / k6 壓測）。
**修復建議：**
```sql
-- 改用 INSERT...SELECT 搭配 FOR UPDATE + RETURNING 驗證最終數量
-- 或在 INSERT 後檢查 COUNT，若超額則 ROLLBACK
WITH cnt AS (
  SELECT COUNT(*) AS c FROM form_responses WHERE form_id = $2 FOR UPDATE
)
INSERT INTO form_responses (...)
SELECT ... FROM cnt WHERE cnt.c < $5
RETURNING id;
```

---

### C-02: 表單檔案上傳 — 路徑所有權驗證可繞過

**檔案：** `backend/app/services/form.py:681-683`
**說明：** fallback 驗證 `elif user_id in parts` 只檢查 user_id 是否出現在路徑任何部分。攻擊者可將自己的 UUID 嵌入檔名，通過驗證以提交他人的檔案。
**重現：** 提交包含 `forms/uploads/{other_user}/{attacker_uuid}_file.pdf` 的回覆。
**修復建議：** 移除 fallback，只允許固定位置的模式比對（`parts[2] == user_id`），不符合即 PermissionError。

---

### C-03: PostDetailView v-html — mXSS 風險

**檔案：** `frontend/src/views/forum/PostDetailView.vue:272`
**說明：** `contentSegments` 經過 sanitize → DOM 操作（加入 card markers）→ 再次 sanitize，但中間的 DOM 重組（`addLinkSafety()` 使用 `innerHTML`）可能產生 Mutation XSS。
**重現：** 建構特殊 HTML payload，利用多次 serialize/parse 迴圈繞過 DOMPurify。
**修復建議：**
```typescript
// 在最終渲染前強制再次 sanitize
<div v-if="seg.type === 'html'" v-html="sanitizeHtml(seg.content)"></div>
```

---

### C-04: Comment/QA 中 renderMentions 後未重新 sanitize

**檔案：** `frontend/src/views/forum/PostDetailView.vue:506,614`、`frontend/src/views/qa/QADetailView.vue:347`
**說明：** `renderMentions()` 在已 sanitize 的 HTML 上進行 DOM walk 並插入 `<span>` 元素。雖然函式最後對 `container.innerHTML` 做 sanitize，但 text node 替換可能產生新的 HTML 結構，導致 mXSS。
**修復建議：** 在 `v-html` 綁定處額外包一層 `sanitizeHtml()`：
```vue
<p v-html="sanitizeHtml(renderMentions(sanitizeHtml(node.root.content), node.root.mentions))"></p>
```

---

### C-05: .env 檔案含真實超級管理員密碼

**檔案：** `.env:79-80`
**說明：** `SUPER_ADMIN_PASSWORD=rVXRWwCdHbwzVbgB6xN2z-lb8FepRqpT` 明文存在。若 .env 未正確 gitignore 或被意外部署，憑證即洩露。
**修復建議：**
1. 確認 `.env` 在 `.gitignore` 中
2. 檢查 git 歷史是否曾提交過 `.env`（若有，立即更換密碼）
3. 生產環境使用 secrets manager（如 Docker Secrets / Vault）

---

### C-06: 開發環境預設密碼可能被複製到生產

**檔案：** `.env:5,16,48,56`
**說明：** `changeme_postgres`、`changeme_redis`、`changeme_minio` 等弱密碼。若運維人員直接複製 `.env` 到生產伺服器，所有服務均使用弱憑證。
**修復建議：** 在 `config.py` 的 `model_validator` 中，若 `FASTAPI_ENV == "production"` 且密碼含 `changeme`，直接 `raise ValueError` 阻止啟動。

---

### C-07: CSV 注入 sanitize 不完整

**檔案：** `backend/app/services/dm.py:188-212`
**說明：** `_sanitize_csv_content()` 只處理首字元為 `=`, `+`, `-`, `@`, `\t`, `\r` 的情況。但 Excel 會執行引號內的公式（如 `"=1+1"`），可繞過首字元檢查。
**修復建議：** 對所有欄位加上 `'` 前綴（tab-prefixing），或改用 `.txt` 純文字格式匯出。

---

## HIGH — 上線首週內修復

### H-01: Client-Side Role 可被篡改（TOCTOU 視窗）

**檔案：** `frontend/src/stores/auth.ts:20-21,32-38`
**說明：** `role` 和 `expiresAt` 存在 localStorage，路由守衛在 `verifySession()` 完成前即依此判斷權限。攻擊者可在 DevTools 中將 `role` 改為 `SUPER_ADMIN`，在 session 驗證到達前短暫看到管理介面。
**修復建議：** 在 `main.ts` 中 `await auth.verifySession()` 完成前不掛載 App（或對管理路由加 loading gate）。

---

### H-02: 後端例外資訊洩漏

**檔案：** `backend/app/api/v1/endpoints/admin.py:104`、`backend/app/api/v1/endpoints/forms.py:81`
**說明：** `raise AppError(..., str(e))` 直接將內部例外訊息傳回客戶端，可能洩漏檔案路徑、SQL 錯誤或連線資訊。
**修復建議：** 所有面向使用者的錯誤回應使用固定訊息，將 `str(e)` 僅記入 server log。

---

### H-03: User Role 更新缺乏行級鎖

**檔案：** `backend/app/repositories/user_repo.py:127-135`
**說明：** `update_role()` 未使用 `FOR UPDATE`，兩個並行的角色變更可產生不一致的最終狀態。
**修復建議：** `SELECT ... FOR UPDATE` + 單一交易包裝。

---

### H-04: DM 檔案刪除在交易外執行

**檔案：** `backend/app/services/dm.py:410-455`
**說明：** 訊息超過字數上限時刪除舊訊息，MinIO 檔案刪除在 DB 刪除之後但不在同一交易中。若 MinIO 刪除失敗，檔案成為孤兒且儲存配額無法歸還。
**修復建議：** 先標記為 pending_delete → DB commit → MinIO 刪除 → 確認後清除標記；失敗的由 cleanup job 處理。

---

### H-05: 生產環境 DATABASE_SSL 預設為 false

**檔案：** `backend/app/core/config.py:65-66`、`.env.production.example:30`
**說明：** `DATABASE_SSL=false` 只觸發警告，不阻止啟動。生產資料庫連線可能未加密。
**修復建議：** 若 `FASTAPI_ENV == "production"` 且 PG host 非 localhost，強制要求 `DATABASE_SSL=true`。

---

### H-06: CORS 驗證僅警告不阻止

**檔案：** `backend/app/core/config.py:108-124`
**說明：** wildcard origin (`*`) 和無 `http://` 前綴的 origin 只觸發 warning，不 raise error。
**修復建議：** 在 production 環境下，不合法 CORS origin 應直接 `raise ValueError`。

---

### H-07: Redis maxmemory 256MB + allkeys-lru 可能踢掉 session

**檔案：** `redis/redis-prod.conf:4-5`
**說明：** `allkeys-lru` 策略會無差別淘汰所有 key，包括 session 和 Celery 任務結果。256MB 對生產環境偏小。
**修復建議：**
```conf
maxmemory 1gb          # 依實際需求調整
maxmemory-policy volatile-lru  # 只淘汰設有 TTL 的 key
```

---

### H-08: PostgreSQL max_connections=50 可能不足

**檔案：** `docker-compose.yml:120`
**說明：** 4 個 FastAPI worker + Celery worker + Beat + migrate = 每個 worker 可能用 10-30 連線，50 上限容易耗盡。
**修復建議：** 生產設為 `max_connections=200`（或依 worker 數 × pool_size + 20% overhead 計算）。

---

### H-09: X-Real-IP 信任未驗證代理 IP

**檔案：** `backend/app/core/rate_limit.py:33-43`
**說明：** `get_client_ip()` 信任任何 `X-Real-IP` header，攻擊者可偽造 IP 繞過 rate limit。
**修復建議：** 只在 `request.client.host` 是受信任的代理 IP 時，才讀取 `X-Real-IP`。

---

### H-10: Presigned URL 過期與 attachment_expires_at 不同步

**檔案：** `backend/app/services/dm.py:490-494`
**說明：** Presigned URL 有效期可能長於 `attachment_expires_at`，使用者可在附件「過期」後仍透過有效的 presigned URL 存取檔案。
**修復建議：** 產生 presigned URL 前檢查 `attachment_expires_at < NOW()`，若已過期則回 403。

---

### H-11: SIG 成員數 decrement 非原子操作

**檔案：** `backend/app/repositories/sig_repo.py:177-192,251-263`
**說明：** DELETE member 和 UPDATE member_count 分兩步驟，若第二步失敗，count 與實際不一致。
**修復建議：** 包在同一交易中，或改用資料庫 trigger 自動維護。

---

### H-12: 缺少 HTTPS 自動重導

**檔案：** `nginx/conf.d/default.conf:285-298`
**說明：** HTTP → HTTPS 重導被注釋，需 docker-entrypoint.sh 解注釋。若 entrypoint 未正確執行，HTTP 明文通訊暴露憑證。
**修復建議：** 確認生產部署流程中 HTTPS redirect 已啟用；加入 health check 驗證。

---

### H-13: DEBUG 模式下 stack trace 暴露

**檔案：** `.env:23`
**說明：** `FASTAPI_DEBUG=true` 會暴露 stack trace、OpenAPI docs。若被複製到生產，攻擊者可利用錯誤訊息中的路徑和變數資訊。
**修復建議：** 在 `config.py` 中，若 `FASTAPI_ENV == "production"` 且 `FASTAPI_DEBUG == true`，raise error。

---

### H-14: Celery 全域 soft_time_limit 可能中斷長任務

**檔案：** `backend/app/celery_app.py:34-35`
**說明：** 全域 `task_soft_time_limit=300`（5 分鐘），但 `cleanup_orphan_files` 設有 3500s 個別 soft limit。若 Celery 使用較嚴格的全域值，該任務可能被提前終止。
**修復建議：** 確認每個任務的 `soft_time_limit` 覆蓋全域值；或將全域值提高至最長任務的時限。

---

## MEDIUM — 上線首月內修復

### M-01: WebSocket 訊息內容未深度驗證

**檔案：** `frontend/src/composables/useWebSocket.ts:118-183`
**說明：** WS 訊息只檢查 `typeof msg.type === 'string'`，message body 直接傳入 store。若伺服器端遭入侵或 MITM，惡意 payload 可注入。
**修復建議：** 使用 `assertShape()` 或 Zod 驗證所有 WS message 欄位。

---

### M-02: Guest Counter 初始化競態

**檔案：** `backend/app/services/auth.py:160-193`
**說明：** 多進程同時初始化 guest counter 時，各自 SCAN 後 SET NX，第一個寫入的可能基於過時的 count。
**修復建議：** 改用 Lua script 原子執行 scan+set。

---

### M-03: 表單回覆數量非即時一致

**檔案：** `backend/app/repositories/form_repo.py:125-148`
**說明：** `response_count` 透過 LEFT JOIN subquery 取得，與表單資料非同一交易，可能顯示過時的數字。
**影響：** 使用者看到的回覆數與實際不符（差異通常 ≤1）。

---

### M-04: Cursor 編碼使用 pipe 分隔 — 特殊值可能破壞解析

**檔案：** `backend/app/repositories/post_repo.py:62-76`
**說明：** `_decode_cursor()` 用 `|` 分隔 sort/value/uuid，若 value 含 pipe 則解析錯誤。
**修復建議：** 改用 JSON + base64 編碼。

---

### M-05: 搜尋 fallback count 缺少 LEFT JOIN

**檔案：** `backend/app/repositories/post_repo.py:599-606`
**說明：** 搜尋頁數超出範圍時的 count query 使用 LEFT JOIN sigs，但 WHERE 子句可能過濾掉 sig_id 為 NULL 的貼文，導致 total 偏低。

---

### M-06: 共同作者編輯權限在並行狀態變更下可能不一致

**檔案：** `backend/app/services/post.py:218-223`
**說明：** 權限檢查與實際編輯不在同一交易的 lock scope 內。

---

### M-07: Notification unread_count 與分頁資料不在同一交易

**檔案：** `backend/app/repositories/notification_repo.py:95-107`
**說明：** 取得分頁通知和 unread_count 之間可能新增通知，導致數字不一致。

---

### M-08: SIG 刪除時可能遺漏通知清理

**檔案：** `backend/app/repositories/sig_repo.py:118-123`
**說明：** 只刪除了與 SIG 貼文相關的通知，與成員邀請、角色變更相關的通知可能成為孤兒。

---

### M-09: SIG admin count 檢查不一致

**檔案：** `backend/app/repositories/sig_repo.py:233-248`
**說明：** `count_admins()` 使用 FOR UPDATE，但部分移除成員的程式碼路徑未鎖定，TOCTOU 可讓最後一個 admin 離開。

---

### M-10: Cursor sort 與請求 sort 不匹配時沒有驗證

**檔案：** `backend/app/repositories/post_repo.py:347-365`
**說明：** cursor 內嵌 sort 類型，但若前端切換排序卻沿用舊 cursor，分頁結果將跳躍或重複。

---

### M-11: DM 對話 updated_at 未在 recall 時更新

**檔案：** `backend/app/repositories/dm_repo.py:314-336`
**說明：** recall 訊息不更新 `updated_at`，對話列表排序不反映最新操作。

---

### M-12: DM read receipt 回傳 MIN(read_at)

**檔案：** `backend/app/repositories/dm_repo.py:339-366`
**說明：** 批次標記已讀後回傳 `MIN(read_at)` 而非 `MAX(read_at)`，可能讓前端顯示過早的已讀時間。
**修復建議：** 改用 `MAX(read_at)`。

---

### M-13: 表單統計除以零邊界

**檔案：** `backend/app/services/form.py:164-184`
**說明：** `_normalize_percentages()` 對全零百分比的邊界處理可能產生 NaN。

---

### M-14: 表單 question options 缺乏唯一性驗證

**檔案：** `backend/app/services/form.py:59-65`
**說明：** 選擇題 options 未驗證 `id` 唯一性，重複 id 會使統計合併計算。

---

### M-15: 文字回覆空白字串被計為有效回覆

**檔案：** `backend/app/services/form.py:276-278`
**說明：** `value != ""` 不排除純空白（如 `"   "`），統計中會膨脹回覆數。
**修復建議：** `if value.strip():`

---

### M-16: Admin endpoint 缺少 rate limit

**檔案：** `backend/app/api/v1/endpoints/admin.py:29-106`
**說明：** `/dashboard` 等聚合查詢無頻率限制，admin 可反覆觸發昂貴 SQL。

---

### M-17: Filename Content-Disposition header 潛在注入

**檔案：** `backend/app/api/v1/endpoints/files.py:346-349`
**說明：** regex `[^\w.\-]` 已移除多數危險字元，但未過濾 `"` 或 `\r\n`。
**修復建議：** 額外 `re.sub(r'["\\\r\n]', "_", safe_filename)`。

---

### M-18: 生產 nginx 缺少 CSP nonce

**檔案：** `nginx/snippets/security-headers.conf.template:15`
**說明：** `script-src 'self'` 已足夠安全，但 `style-src 'unsafe-inline'` 削弱了 CSP（Tailwind 需要）。

---

### M-19: Audit log endpoint user_id 未驗 UUID 格式

**檔案：** `backend/app/api/v1/endpoints/users.py:613-631`
**說明：** `user_id: str | None` 直接傳入 SQL，格式不符的字串可能引發 500 或洩漏錯誤訊息。

---

### M-20: Cloudflare Tunnel token 從 .env 載入

**檔案：** `docker-compose.prod.yml:304-328`
**說明：** `CLOUDFLARE_TUNNEL_TOKEN` 是高敏感度 secret，存在 .env 檔有被讀取的風險。建議使用 Docker Secrets 或環境變數注入。

---

### M-21: COOKIE_DOMAIN 在 .env.production.example 未設實際值

**檔案：** `.env.production.example:62-67`
**說明：** 空值可能導致跨子網域認證失敗。

---

### M-22: 缺少 X-Request-ID 全鏈路追蹤

**檔案：** nginx → FastAPI
**說明：** nginx 日誌中有 request_id，但 FastAPI 未傳遞至應用日誌，難以跨服務關聯排查。

---

### M-23: 前端 useFormSubmit 缺少 AbortController

**說明：** 使用者快速雙擊提交按鈕可能觸發重複請求。雖有 `submitting` flag，但在網路慢時仍有視窗。
**修復建議：** 加入 AbortController，離開頁面時取消進行中的請求。

---

### M-24: Pagination offset 模式與 cursor 模式切換不一致

**檔案：** `backend/app/repositories/post_repo.py:459-463`
**說明：** fallback count 的 JOIN 邏輯可能與主查詢不同，導致 total 偏差。

---

### M-25: 使用者匿名化未刪除 MinIO 中的 avatar 檔案

**檔案：** `backend/app/repositories/user_repo.py:166-195`
**說明：** `avatar_url = NULL` 但實體檔案仍在 MinIO，透過 URL 仍可存取。
**修復建議：** 匿名化前先呼叫 `delete_object()` 刪除檔案。

---

## LOW — 排入待辦

### L-01: requirements.txt 版本範圍過寬 ✅ FIXED

所有套件已收窄至合理的上限範圍（如 `fastapi>=0.110.0,<0.120.0`、`pydantic>=2.5.0,<3.0.0`）。

### L-02: 開發環境 port 暴露

`docker-compose.override.yml` 暴露 15432/16379/19000 至 localhost。開發環境可接受，但需確認生產 compose 不含此設定。

### L-03: Audit log 寫入失敗靜默 ✅ FIXED

新增 `_CRITICAL_AUDIT_EVENTS` 集合（`audit.action`、`user.role_changed`、`user.banned`）。關鍵審計事件永久失敗或 Redis 持久化失敗時，日誌升級為 `CRITICAL` 級別；非關鍵事件從 `warning` 升級為 `error`。8 個新測試。

### L-04: Datadog APM 可能暴露敏感 request/response

`docker-compose.yml:267-290` Datadog agent 未設敏感欄位過濾規則。

### L-05: Guest invite code 無使用對象限制

任何人拿到 invite code 都能註冊 Guest，無法限制特定受邀者。

### L-06: robots.txt Disallow: / 影響 SEO

若網站需要被索引，應調整 robots.txt。

### L-07: 缺少 DNSSEC / DoH 配置

nginx OCSP stapling 使用 8.8.8.8，有 DNS 隱私疑慮。

### L-08: 前端 Draft 存 localStorage 可被 XSS 讀取

`ai3l_post_draft_*`、`ai3l_form_draft_*` 含使用者內容。若發生 XSS，草稿洩漏。

### L-09: WebSocket ticket rate limit 與 connection limit 不一致

Rate limit 允許 10 ticket/min，但 WS 連線上限為 5。多餘 ticket 可囤積。

### L-10: Co-author 邀請缺少重複檢查

快速雙擊邀請可能建立重複紀錄。
**修復建議：** 加 UNIQUE constraint `(post_id, invitee_id, status='PENDING')`。

### L-11: Form stats 大量回覆記憶體壓力

`iter_responses_batched` 雖已串流處理，但 metadata dict 隨問題數增長。100k+ 回覆時需監控。

### L-12: 前端 DOMPurify 版本需持續更新

`^3.3.2` 目前安全，但需每月檢查 CVE。

### L-13: CSP 允許 blob: 和 data: for img-src

需要用於圖片預覽和 avatar，但擴大了攻擊面。

### L-14: 無 HTTP/2 Server Push

效能最佳化項目，非安全問題。

### L-15: SIG 刪除後 co-author 孤兒紀錄

SIG 刪除串聯 DELETE posts 上的 coauthors，但若 FK 不嚴格可能殘留。

### L-16: 前端心跳 timeout 15 秒偏長

考慮將 heartbeat 專用 timeout 縮短至 5 秒。

---

## 已確認的安全亮點

以下機制經審計確認為正確實作：

- Argon2 密碼雜湊（含 timing oracle 防護 `_DUMMY_HASH`）
- JWT + HttpOnly cookie + CSRF double-submit
- 全部 SQL 使用 `$1, $2, ...` 參數化（無直接字串拼接）
- 檔案上傳：magic number 檢查、EXIF 移除、PDF sanitize、VirusTotal 掃描
- Session blacklist（Redis JWT revocation）
- Cookie: HttpOnly + Secure + SameSite
- RBAC: `require_role()` 依賴注入全面覆蓋
- WebSocket: 一次性 ticket + Redis atomic validation
- Body size limit: 每個 endpoint 獨立設定
- `allkeys-lru` + AOF persistence（需調整 maxmemory）
- nginx `server_tokens off` + security headers
- DOMPurify + FORCE_BODY mXSS 預防

---

## 建議修復優先順序

### 🔴 上線前（P0）
1. C-01 ~ C-07（所有 Critical）
2. H-05（DATABASE_SSL）
3. H-13（DEBUG mode guard）
4. H-12（HTTPS redirect 確認）

### 🟠 上線首週（P1）
5. H-01 ~ H-04, H-06 ~ H-11, H-14（所有 High）

### 🟡 上線首月（P2）
6. M-01 ~ M-25（所有 Medium）

### 🟢 持續改善（P3）
7. L-01 ~ L-16（所有 Low）

---

*本報告由四組平行靜態分析代理程式產生，涵蓋後端安全、前端安全、基礎設施配置、業務邏輯四個面向。*
