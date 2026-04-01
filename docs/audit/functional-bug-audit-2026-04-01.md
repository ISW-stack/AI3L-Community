# 功能性 Bug 審計報告

**日期:** 2026-04-01
**審計範圍:** 全端功能性 Bug（後端 API、前端 UI、前後端整合）
**方法:** 靜態程式碼分析，逐一驗證原始碼

---

## 摘要

| 嚴重度 | 數量 |
|--------|------|
| High   | 2    |
| Medium | 5    |
| Low    | 6    |
| **總計** | **13** |

---

## High 嚴重度

### H-01: EXIF 元數據清除功能完全失效

- **檔案:** `backend/app/core/file_validation.py:209`
- **影響:** 所有圖片上傳（編輯器、頭像）

**問題描述:**

`strip_exif_metadata()` 呼叫了 Pillow 中不存在的方法：

```python
# 錯誤：Pillow 無此方法
clean.putdata(list(img.get_flattened_data()))
```

`Image.get_flattened_data()` 在任何版本的 Pillow（包括 `>=12.1.1`）中均不存在。正確方法為 `img.getdata()`。

由於外層有 `except Exception: return data` 捕獲，上傳不會失敗，但 **EXIF 清除永遠不執行**。所有上傳圖片的 GPS 座標、裝置序號、拍攝時間等 EXIF 元數據均被完整保留。

**修復方向:**

```python
clean.putdata(list(img.getdata()))
```

---

### H-02: 訪客登入邀請碼失敗時洩漏全域 Guest 容量

- **檔案:** `backend/app/api/v1/endpoints/auth.py:183-189`
- **影響:** 訪客登入容量管理

**問題描述:**

在 `login_as_guest` 中，當 `consume_invite_code` 失敗時的錯誤路徑：

```python
result = await guest_login(req.display_name)  # ← 成功：全域計數器 +1，Redis session 建立
# ...
consumed = await consume_invite_code(invite_code)
if not consumed:
    await decrement_guest_ip_counter(ip)   # ← 僅撤銷 IP 計數
    # ← 未呼叫 decrement_guest_counter()
    # ← 未呼叫 destroy_session()
    raise AppError(...)
```

每次發生此情況會永久佔用一個 guest 容量槽位（直至伺服器重啟），且孤立的 Redis session 殘留直到 TTL 過期。重複的邀請碼競爭情況（如併發提交）將持續累積洩漏，最終導致所有訪客無法登入。

**修復方向:** 錯誤路徑中補充呼叫 `await decrement_guest_counter()` 和 `await destroy_session(jti)`。

---

## Medium 嚴重度

### M-01: `dm_friends_only` 前後端不一致 — 隱私提示永遠不顯示

- **後端:** `backend/app/schemas/user.py:41-53`（`PublicUserResponse`）
- **前端:** `frontend/src/views/UserProfileView.vue:206-218`
- **影響:** DM 隱私設定的視覺提示

**問題描述:**

後端 `PublicUserResponse` schema 不包含 `dm_friends_only` 欄位（因隱私原因已移除），但前端 `UserProfileView` 仍依賴此欄位：

```html
<!-- 此條件永遠為 false，因後端不回傳此欄位 -->
:title="user?.dm_friends_only ? 'This user only accepts messages from friends' : 'Send message'"
<Lock v-if="user?.dm_friends_only" ... />
```

結果：**使用者永遠無法從對方個人頁面得知對方開啟了「僅限朋友傳訊」設定**，發送後才收到 403 錯誤。

---

### M-02: 密碼特殊字元驗證規則前端不一致

- **檔案 A:** `frontend/src/views/RegisterView.vue:74`
- **檔案 B:** `frontend/src/views/HomeView.vue:74`
- **影響:** 會員申請流程

**問題描述:**

| 位置 | 正則 | 允許範圍 |
|------|------|----------|
| RegisterView（帳號註冊） | `/[^A-Za-z0-9]/` | 任何非字母數字字元 |
| HomeView（會員申請） | `/[!@#$%^&*()_+\-=\[\]{}|;:,.<>?\/~]/` | 僅列舉的特殊字元 |

含有反引號（`` ` ``）、雙引號（`"`）、非 ASCII 字元等密碼在一個流程中通過但在另一個中被拒，造成使用者困惑。

---

### M-03: 表單上傳檔案對表單管理員不可存取（403）

- **檔案:** `backend/app/api/v1/endpoints/files.py:290-297`
- **影響:** SIG 管理員、表單建立者查看回覆中的檔案

**問題描述:**

`serve_file` 端點的非 editor 檔案存取邏輯：

```python
if not is_editor_file and not is_admin:
    owns_file = key.startswith(f"avatars/{current_user['sub']}")
    if not owns_file:
        raise AppError(ErrorCode.SYS_403, ...)
```

表單上傳檔案路徑為 `forms/uploads/{form_id}/...`，不符合 `avatars/{user_id}` 的擁有者模式。**SIG 管理員和表單建立者若非站台管理員，無法透過此端點查看回覆中的檔案上傳，一律回傳 403**。

---

### M-04: `GET /users/me` 允許 Guest 但必定回傳 404

- **檔案:** `backend/app/api/v1/endpoints/users.py:59-65`
- **影響:** API 契約一致性

**問題描述:**

端點宣告允許 `GUEST` 角色存取：

```python
current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST"))
```

但 Guest 在 `users` 表中無記錄，`get_user_by_id()` 必定回傳 `None`，觸發 404。前端 `fetchProfile()` 對 GUEST 提前返回（`if role.value === 'GUEST') return`）避開了此問題，但直接呼叫 API 的 Guest 會收到誤導性的 404 而非明確的說明。

---

### M-05: 未儲存變更對話框為硬編碼英文（未翻譯）

- **檔案:** `frontend/src/views/forum/PostCreateView.vue:209`
- **影響:** 非英語使用者

**問題描述:**

```js
return window.confirm('You have unsaved changes. Are you sure you want to leave?')
```

應用已支援 17 種語言，此對話框卻使用硬編碼英文字串而非 `t()` 翻譯函式，非英語使用者離開編輯頁面時會看到英文確認框。

---

## Low 嚴重度

### L-01: `SigMembersView` / `SigFormsView` 掛載時觸發雙重 API 請求

- **檔案:** `frontend/src/views/sigs/SigMembersView.vue:156-161`、`SigFormsView.vue:68-72,225`

`onMounted(fetchMembers)` 和 `watch(userSigRole, fetchMembers)` 在元件初始化時同時觸發，造成每次進入頁面發送兩次相同請求。

---

### L-02: `FormsDirectoryView` 搜尋時觸發雙重請求

- **檔案:** `frontend/src/views/forms/FormsDirectoryView.vue:43-45,228`

搜尋輸入時 `setPage(1)` 透過 `watch(page)` 觸發 `fetchForms()`，同時防抖計時器到期也再次呼叫 `fetchForms()`，造成重複請求。

---

### L-03: `ApplicationsView` / `AuditLogsView` 日期格式硬編碼 `en-US`

- **檔案:** `frontend/src/views/admin/ApplicationsView.vue:69-75`、`AuditLogsView.vue:90-96`

兩處均使用本地 `formatDate` 函式硬編碼 `'en-US'` locale，未使用 `@/utils/date` 中支援使用者語系的 `formatDate(date, locale)` 工具。

---

### L-04: `UserProfileView` DM 相關文字硬編碼英文

- **檔案:** `frontend/src/views/UserProfileView.vue:207-213`

"Message"、"Send message"、"This user only accepts messages from friends" 均未使用 `t()` 翻譯，在非英語介面下顯示英文。

---

### L-05: `SiteSettingsView` 搜尋防抖計時器未在元件銷毀時清除

- **檔案:** `frontend/src/views/admin/SiteSettingsView.vue:163,203`

`onChairSearchInput` 和 `onCoChairSearchInput` 建立的 `setTimeout` 計時器無對應的 `onUnmounted` 清除邏輯，離開頁面後計時器可能觸發並寫入已銷毀的 ref。

---

### L-06: `NotificationsView` 清除全部後未重置分頁狀態

- **檔案:** `frontend/src/views/NotificationsView.vue:116-126`

`confirmClearAll()` 成功後清空本地通知列表但未重置分頁狀態，若使用者在非第一頁執行清除，UI 的分頁資訊與實際數據不一致。

---

## 附錄：已確認為非 Bug 的項目

| 項目 | 結論 |
|------|------|
| Admin UsersView 顯示 SUPER_ADMIN 功能給 ADMIN | **非 Bug** — 已用 `v-if="auth.isSuperAdmin"` 正確隱藏 |
| Guest 申請會員後無法查看申請狀態 | **非 Bug** — 申請流程建立真實 DB 記錄，同 session 可正確查詢 |
| DM 對話列表在所有訊息撤回後的顯示 | **非 Bug** — `LEFT JOIN LATERAL` 行為正確 |
| 審計日誌路由 SUPER_ADMIN 守衛 | **非 Bug** — 前後端均正確設定 |
