# AI3L Community UI/UX 完整施工計畫 v3.0

> **Scope**: 全站 Design System 建立 + 元件庫 + 行動裝置響應式 + 無障礙基礎
> **Tech Stack**: Vue 3 (Composition API) + Vite 6 + Tailwind CSS v4 (`@theme`) + Pinia
> **Font**: Inter Variable (唯一字體，本地打包)
> **Icons**: Lucide Vue Next (Tree-shakable SVG)
> **原則**: 零外部 CDN、純英文介面、零技術債

---

## 目錄

1. [系統現況分析](#1-系統現況分析)
2. [Design Token 規範](#2-design-token-規範)
3. [共用元件庫規格](#3-共用元件庫規格)
4. [響應式策略](#4-響應式策略)
5. [無障礙 (a11y) 基礎規範](#5-無障礙-a11y-基礎規範)
6. [施工階段與步驟](#6-施工階段與步驟)
7. [逐頁改造清單](#7-逐頁改造清單)
8. [驗證檢查表](#8-驗證檢查表)

---

## 1. 系統現況分析

### 1.1 架構現狀

| 維度 | 現狀 |
|---|---|
| CSS 框架 | Tailwind v4，零自訂 `@theme`，`style.css` 只有 `@import 'tailwindcss'` |
| 字體 | 無。完全依賴瀏覽器/系統預設 sans-serif |
| 圖標 | 無圖標庫。首頁使用 Unicode Emoji (🔑📝👀)，其餘為內嵌 SVG |
| 元件庫 | 無。所有 UI 樣式散落在 20+ 個 `.vue` 檔案中 |
| 響應式 | 極度不足。20 個 View 中僅 5 個有 breakpoint class |
| 深色模式 | 無。零個 `dark:` class |
| 無障礙 | 無。零個 `aria-*` 屬性 |

### 1.2 重複樣式統計（技術債來源）

以下 class 組合在全站重複出現超過 10 次以上：

| 模式 | 重複次數 | 目標 |
|---|---|---|
| `bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700` | 20+ | → `<BaseButton>` |
| `w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500` | 20+ | → `<BaseInput>` |
| `bg-white rounded-xl shadow p-{4-6}` | 30+ | → `<BaseCard>` |
| `bg-{color}-50 border border-{color}-200 text-{color}-700 rounded-lg p-3 text-sm` | 15+ | → `<BaseAlert>` |
| `text-xs px-2 py-0.5 rounded-full bg-{color}-100 text-{color}-700` | 12+ | → `<BaseBadge>` |
| `fixed inset-0 bg-black/40 flex items-center justify-center z-50` | 5 | → `<BaseModal>` |
| `bg-white rounded-xl shadow overflow-hidden` + `<table>` 結構 | 5 | → `<BaseTable>` |

### 1.3 已知不一致問題

1. **按鈕尺寸不統一**：Primary button 的 padding 在各頁面使用 `py-1` / `py-1.5` / `py-2` / `py-2.5` 不等
2. **Select 元素缺少 focus 樣式**：多數 `<select>` 沒有 `focus:ring-*`，與 `<input>` 不一致
3. **Modal overlay 不一致**：一般 modal 用 `bg-black/40`，PrivacyConsent 用 `bg-black/60`
4. **GuestLoginView 按鈕色彩偏離**：使用 `bg-gray-700` 而非系統 primary blue
5. **Navbar Logo 色彩偏離**：唯一使用 `text-blue-700` 的地方，全站其餘均使用 `text-blue-600`

---

## 2. Design Token 規範

所有設計變數統一定義在 `src/style.css` 的 `@theme` 區塊中。任何 `.vue` 檔案**禁止**使用 Tailwind 原始色（如 `blue-600`），必須透過語義化 token 引用。

### 2.1 字體 Token

```css
@theme {
  --font-sans: 'Inter Variable', ui-sans-serif, system-ui, sans-serif;
}
```

只使用一套字體。Inter Variable 支援 100–900 全部字重，透過 `font-light` / `font-normal` / `font-medium` / `font-semibold` / `font-bold` 控制視覺層次，無需第二套字體。

### 2.2 色彩 Token

#### 主色系 (Brand Primary) — 基於 Oxford Blue `#002147`

```css
@theme {
  /* Brand Primary — 學術深藍 */
  --color-brand-50:  #e6eef8;
  --color-brand-100: #b3cce8;
  --color-brand-200: #80a9d8;
  --color-brand-300: #4d87c8;
  --color-brand-400: #2670b8;
  --color-brand-500: #0059a8;
  --color-brand-600: #004a8c;  /* 主要互動色 — 按鈕、連結 */
  --color-brand-700: #003b70;
  --color-brand-800: #002c54;
  --color-brand-900: #002147;  /* Oxford Blue — 深底 */
  --color-brand-950: #001528;

  /* 語義色 — Success */
  --color-success-50:  #ecfdf5;
  --color-success-100: #d1fae5;
  --color-success-500: #10b981;
  --color-success-600: #059669;
  --color-success-700: #047857;

  /* 語義色 — Warning */
  --color-warning-50:  #fffbeb;
  --color-warning-100: #fef3c7;
  --color-warning-500: #f59e0b;
  --color-warning-600: #d97706;
  --color-warning-700: #b45309;

  /* 語義色 — Danger */
  --color-danger-50:  #fef2f2;
  --color-danger-100: #fee2e2;
  --color-danger-500: #ef4444;
  --color-danger-600: #dc2626;
  --color-danger-700: #b91c1c;

  /* 語義色 — Info */
  --color-info-50:  #eff6ff;
  --color-info-100: #dbeafe;
  --color-info-500: #3b82f6;
  --color-info-600: #2563eb;
  --color-info-700: #1d4ed8;

  /* 中性色 (Neutral) — 自訂灰階 */
  --color-surface:     #ffffff;
  --color-surface-alt: #f9fafb;
  --color-border:      #e5e7eb;
  --color-muted:       #6b7280;
  --color-foreground:  #111827;
}
```

#### 色彩遷移對照表

| 現有 class | 遷移至 | 語義 |
|---|---|---|
| `bg-blue-600` | `bg-brand-600` | 主要按鈕、連結 |
| `hover:bg-blue-700` | `hover:bg-brand-700` | 按鈕 hover |
| `text-blue-600` | `text-brand-600` | 連結文字 |
| `focus:ring-blue-500` | `focus:ring-brand-500` | Input focus |
| `bg-blue-50` | `bg-brand-50` | 輕底色 |
| `bg-blue-100 text-blue-700` | `bg-brand-100 text-brand-700` | Badge (MEMBER) |
| `bg-red-50 text-red-700` | `bg-danger-50 text-danger-700` | Error alert |
| `bg-red-600` | `bg-danger-600` | 危險按鈕 |
| `bg-green-50 text-green-700` | `bg-success-50 text-success-700` | Success alert |
| `bg-green-600` | `bg-success-600` | Approve 按鈕 |
| `bg-yellow-50 text-yellow-700` | `bg-warning-50 text-warning-700` | Warning alert |
| `bg-gray-50` | `bg-surface-alt` | 次要背景 |
| `bg-white` | `bg-surface` | 主要背景 |
| `text-gray-900` | `text-foreground` | 主要文字 |
| `text-gray-500` / `text-gray-600` | `text-muted` | 輔助文字 |
| `border-gray-200` | `border-border` | 邊框 |

> **注意**：`orange-*`（ADMIN badge）和 `purple-*`（SUB_ADMIN badge）可保留 Tailwind 原始色，因為它們僅用於角色區分，屬於裝飾性用途，不在核心語義色系統內。或者也可定義額外 token，視需求而定。

### 2.3 間距與圓角 Token

```css
@theme {
  --radius-sm: 0.375rem;   /* 6px — badge, small pill */
  --radius-md: 0.5rem;     /* 8px — button, input */
  --radius-lg: 0.75rem;    /* 12px — card, modal */
  --radius-full: 9999px;   /* pill shape */
}
```

---

## 3. 共用元件庫規格

所有共用元件放置於 `src/components/base/` 目錄下。

### 3.1 `BaseButton.vue`

**Props:**

| Prop | Type | Default | 說明 |
|---|---|---|---|
| `variant` | `'primary' \| 'secondary' \| 'danger' \| 'success' \| 'ghost' \| 'soft-danger' \| 'soft-success'` | `'primary'` | 按鈕視覺風格 |
| `size` | `'sm' \| 'md' \| 'lg' \| 'full'` | `'md'` | 按鈕尺寸 |
| `disabled` | `boolean` | `false` | 停用狀態 |
| `loading` | `boolean` | `false` | 載入中（顯示 spinner，禁止點擊） |
| `as` | `'button' \| 'a' \| 'router-link'` | `'button'` | 渲染元素類型 |

**樣式映射：**

```
primary:      bg-brand-600 text-white hover:bg-brand-700
secondary:    bg-surface-alt text-muted border border-border hover:bg-gray-100
danger:       bg-danger-600 text-white hover:bg-danger-700
success:      bg-success-600 text-white hover:bg-success-700
ghost:        text-brand-600 hover:underline (無背景)
soft-danger:  bg-danger-50 text-danger-600 hover:bg-danger-100
soft-success: bg-success-50 text-success-600 hover:bg-success-100

size sm:   px-3 py-1.5 text-xs rounded-md
size md:   px-4 py-2   text-sm rounded-lg
size lg:   px-6 py-2.5 text-sm rounded-lg
size full: w-full py-2.5 text-sm rounded-lg font-medium
```

### 3.2 `BaseInput.vue`

**Props:**

| Prop | Type | Default | 說明 |
|---|---|---|---|
| `modelValue` | `string \| number` | — | v-model 繫結 |
| `type` | `string` | `'text'` | input type |
| `label` | `string` | — | 上方 label 文字 |
| `error` | `string` | — | 下方錯誤訊息（紅色） |
| `disabled` | `boolean` | `false` | 停用狀態 |
| `placeholder` | `string` | — | placeholder |

**包含子元件**：`BaseSelect.vue`（同樣 Props 結構 + `options` array）、`BaseTextarea.vue`。

**統一樣式：**
```
w-full px-3 py-2 border border-border rounded-lg
focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none
text-foreground placeholder:text-muted
disabled → bg-surface-alt text-muted cursor-not-allowed
error → border-danger-500 focus:ring-danger-500
```

### 3.3 `BaseCard.vue`

**Props:**

| Prop | Type | Default | 說明 |
|---|---|---|---|
| `hoverable` | `boolean` | `false` | hover 時 shadow 加強 |
| `padding` | `'sm' \| 'md' \| 'lg'` | `'md'` | 內部間距 |

**樣式：**
```
bg-surface rounded-lg shadow
padding sm: p-4 / md: p-5 / lg: p-6
hoverable → hover:shadow-md transition
```

### 3.4 `BaseAlert.vue`

**Props:**

| Prop | Type | Default | 說明 |
|---|---|---|---|
| `type` | `'error' \| 'success' \| 'warning' \| 'info'` | `'info'` | 語義類型 |
| `dismissible` | `boolean` | `false` | 是否可關閉 |

**樣式映射：**
```
error:   bg-danger-50  border border-danger-100  text-danger-700
success: bg-success-50 border border-success-100 text-success-700
warning: bg-warning-50 border border-warning-100 text-warning-700
info:    bg-info-50    border border-info-100    text-info-700
base:    rounded-lg p-3 text-sm
```

### 3.5 `BaseBadge.vue`

**Props:**

| Prop | Type | Default | 說明 |
|---|---|---|---|
| `variant` | `'brand' \| 'success' \| 'warning' \| 'danger' \| 'neutral' \| 'orange' \| 'purple'` | `'brand'` | 色彩 |
| `size` | `'sm' \| 'md'` | `'sm'` | 尺寸 |

**樣式：**
```
base:    inline-flex items-center font-medium rounded-full
size sm: text-xs px-2 py-0.5
size md: text-xs px-2.5 py-1

brand:   bg-brand-100 text-brand-700
success: bg-success-100 text-success-700
warning: bg-warning-100 text-warning-700
danger:  bg-danger-100 text-danger-700
neutral: bg-gray-100 text-gray-600
orange:  bg-orange-100 text-orange-700
purple:  bg-purple-100 text-purple-700
```

### 3.6 `BaseModal.vue`

**Props:**

| Prop | Type | Default | 說明 |
|---|---|---|---|
| `modelValue` | `boolean` | — | v-model 控制開關 |
| `title` | `string` | — | Modal 標題 |
| `size` | `'sm' \| 'md' \| 'lg' \| 'xl'` | `'md'` | 寬度 |
| `persistent` | `boolean` | `false` | 點擊 overlay 是否可關閉 |

**結構：**
```html
<Teleport to="body">
  <Transition name="modal">
    <!-- Overlay: fixed inset-0 bg-black/40 z-50 -->
    <!-- Content: bg-surface rounded-lg shadow-xl p-6 -->
    <!-- Header: title + close (&times;) button -->
    <!-- Body: <slot /> -->
    <!-- Footer: <slot name="footer" /> -->
  </Transition>
</Teleport>
```

**尺寸映射：**
```
sm: max-w-sm
md: max-w-md
lg: max-w-lg
xl: max-w-2xl max-h-[80vh] overflow-y-auto
```

**無障礙：**
- `role="dialog"` + `aria-modal="true"` + `aria-labelledby`
- 開啟時 focus trap (Tab 鍵不會離開 modal)
- `Escape` 鍵關閉（除非 persistent）
- 開啟時 `body` 鎖定捲動

### 3.7 `BaseTable.vue`

**Props:**

| Prop | Type | Default | 說明 |
|---|---|---|---|
| `columns` | `Array<{ key, label, class? }>` | — | 欄位定義 |
| `rows` | `Array<Record>` | — | 資料列 |
| `loading` | `boolean` | `false` | 載入狀態 |
| `emptyText` | `string` | `'No data'` | 空資料文字 |

**結構：**
```html
<BaseCard padding="none" class="overflow-hidden">
  <table class="w-full text-sm">
    <thead class="bg-surface-alt border-b border-border">
      <tr><th v-for="col" class="text-left px-4 py-3 font-medium text-muted">{{ col.label }}</th></tr>
    </thead>
    <tbody>
      <tr v-for="row" class="border-b border-border last:border-0 hover:bg-surface-alt transition">
        <td class="px-4 py-3"><slot :name="col.key" :row="row">{{ row[col.key] }}</slot></td>
      </tr>
    </tbody>
  </table>
</BaseCard>
```

### 3.8 `BasePagination.vue`

**Props:**

| Prop | Type | Default | 說明 |
|---|---|---|---|
| `currentPage` | `number` | — | 當前頁碼 |
| `totalPages` | `number` | — | 總頁數 |
| `maxVisible` | `number` | `5` | 最多顯示幾個頁碼按鈕 |

統一分頁按鈕外觀，消除目前兩種不同分頁風格（numbered vs prev/next）的不一致。

---

## 4. 響應式策略

### 4.1 斷點定義

使用 Tailwind v4 預設斷點：

| 斷點 | 寬度 | 代表裝置 |
|---|---|---|
| (default) | < 640px | 手機（Mobile） |
| `sm:` | ≥ 640px | 大手機 / 小平板 |
| `md:` | ≥ 768px | 平板 |
| `lg:` | ≥ 1024px | 桌面 |
| `xl:` | ≥ 1280px | 大螢幕 |

### 4.2 全域 Layout

```
App.vue:
  <AppNavbar />
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
    <router-view />
  </main>
```

各頁面**移除**各自的 `max-w-*xl mx-auto py-8 px-4`，統一由 App.vue 的 `<main>` 控制外框。個別頁面如需更窄的寬度（如 Login 表單），在頁面內部使用 `max-w-md mx-auto` 即可。

### 4.3 Navbar 響應式（最關鍵改造）

**現況問題**：Navbar 水平排列所有連結（含 Admin 的 8+ 個連結），無漢堡選單，手機上必然溢出。

**方案**：

```
桌面 (≥ lg):
┌──────────────────────────────────────────────────────┐
│ [Logo]   Forum  SIGs  [Admin Links...]   🔔  [User] │
└──────────────────────────────────────────────────────┘

手機/平板 (< lg):
┌──────────────────────────────────────┐
│ [Logo]              🔔  [☰ 漢堡按鈕] │
└──────────────────────────────────────┘
  ↓ 點擊展開
┌──────────────────────────────────────┐
│ Forum                                │
│ SIGs                                 │
│ ── Admin ──                          │
│ Dashboard                            │
│ Users                                │
│ Applications                         │
│ ...                                  │
│ ── Account ──                        │
│ Profile                              │
│ Log Out                              │
└──────────────────────────────────────┘
```

**實作細節**：
- 漢堡按鈕使用 Lucide `Menu` / `X` icon
- 展開面板使用 `<Transition>` 搭配 `max-height` 動畫
- 展開時鎖定 body scroll（手機上）
- 桌面版隱藏漢堡按鈕：`lg:hidden`
- 桌面版顯示橫向連結：`hidden lg:flex`

### 4.4 各頁面響應式調整

| 頁面 | 現狀 | 調整 |
|---|---|---|
| HomeView | `md:grid-cols-3` (OK) | 保持 |
| LoginView / RegisterView / GuestLoginView | 無 breakpoint | 卡片已有 `max-w-md`，本身就是窄版，不需額外調整 |
| ForumView | 無 breakpoint | 搜尋列改為 `flex-col sm:flex-row` 堆疊；Post 卡片本身單欄已 OK |
| PostDetailView | 無 breakpoint | 文章內容本身流式排版 OK；comment 區域加 `text-sm` 收縮 |
| PostCreateView | 無 breakpoint | 表單本身單欄 OK，keyword 列改 `flex-wrap` |
| SigsDirectoryView | `sm:grid-cols-2 lg:grid-cols-3` (OK) | 保持 |
| SigDetailView | `sm:grid-cols-2` (部分) | Tab 列改 `overflow-x-auto` 防溢出；Members 表格改為卡片式（< sm） |
| ProfileView | 無 breakpoint | 表單本身單欄 OK；Avatar 區域改 `flex-col sm:flex-row` |
| NotificationsView | 無 breakpoint | 通知列表本身單欄 OK；分頁按鈕加 `flex-wrap` |
| Admin 系列（5 個頁面） | 僅 Dashboard 有 | 所有表格加 `overflow-x-auto` 水平捲動容器；行動裝置上表格最小寬度 `min-w-[600px]` |

### 4.5 表格行動裝置策略

Admin 表格在手機上採用**水平捲動**方式（而非重排為卡片），原因：
1. 表格欄位數量多（5 欄），卡片重排視覺混亂
2. 水平捲動是用戶已熟悉的 pattern
3. 實作成本低，不需為每個表格寫兩套 template

```html
<div class="overflow-x-auto -mx-4 sm:mx-0">
  <div class="min-w-[640px] sm:min-w-0">
    <BaseTable ... />
  </div>
</div>
```

---

## 5. 無障礙 (a11y) 基礎規範

### 5.1 互動元素

| 元素 | 要求 |
|---|---|
| 所有 `<button>` | 必須有可見文字或 `aria-label` |
| 圖標按鈕（如通知鈴鐺、漢堡選單） | `aria-label="Open notifications"` |
| Lucide 圖標（裝飾性） | `aria-hidden="true"` |
| 表單 `<input>` | 必須關聯 `<label>` 或使用 `aria-label` |
| `<select>` | 同 input |
| Modal | `role="dialog"` + `aria-modal="true"` + `aria-labelledby` |
| Toast | `role="alert"` + `aria-live="assertive"` |
| 導覽列 | `<nav aria-label="Main navigation">` |

### 5.2 鍵盤導航

- 所有互動元素必須可透過 `Tab` 鍵到達
- Modal 開啟時實作 focus trap
- Dropdown 選單支援 `Escape` 關閉
- 使用 `:focus-visible` 替代 `:focus`，避免滑鼠點擊時出現 focus ring

### 5.3 色彩對比度

Design Token 中的色彩選擇已確保：
- 正文文字 (`text-foreground` `#111827`) 對比白色背景 ≥ 15:1（超過 AAA）
- 輔助文字 (`text-muted` `#6b7280`) 對比白色背景 ≈ 4.6:1（通過 AA）
- 按鈕文字（白色 on `bg-brand-600` `#004a8c`）≈ 7.5:1（通過 AAA）

---

## 6. 施工階段與步驟

### 階段一：基礎設施建置 (Infrastructure)

**步驟 1.1 — 安裝依賴**
```bash
cd frontend
npm install @fontsource-variable/inter lucide-vue-next
```

**步驟 1.2 — 設定字體入口 (`src/main.ts`)**
```ts
import '@fontsource-variable/inter'
```

**步驟 1.3 — 建立 Design Token (`src/style.css`)**

將 `@import 'tailwindcss'` 後方加入完整的 `@theme { ... }` 區塊（依照第 2 節規範）。

**步驟 1.4 — 建立 Base 元件目錄**
```
src/components/base/
  ├── BaseButton.vue
  ├── BaseInput.vue
  ├── BaseSelect.vue
  ├── BaseTextarea.vue
  ├── BaseCard.vue
  ├── BaseAlert.vue
  ├── BaseBadge.vue
  ├── BaseModal.vue
  ├── BaseTable.vue
  └── BasePagination.vue
```

依照第 3 節規格逐一實作。每個元件需：
- 完整的 TypeScript Props 定義
- Slot 支援（彈性內容）
- `aria-*` 無障礙屬性

### 階段二：全站樣式遷移 (Token Migration)

**按照優先序逐頁遷移**，每完成一頁需：
1. 替換硬編碼 Tailwind 色彩 → 語義化 token
2. 替換重複 class → Base 元件
3. 加入缺失的響應式 class
4. 加入 `aria-*` 屬性
5. 視覺回歸測試

遷移順序（依影響範圍由大到小）：

```
第一輪 — 全域元件：
  1. AppNavbar.vue        ← 加入響應式漢堡選單 + Lucide icons
  2. ToastNotification.vue ← 遷至 BaseAlert token
  3. SkeletonLoader.vue   ← 遷移灰階 token
  4. EmptyState.vue       ← 遷移 + Lucide icon
  5. NotificationBell.vue ← 遷移 + Lucide Bell icon

第二輪 — 公開頁面（訪客首先看到的）：
  6. HomeView.vue         ← Hero Section 重塑 + Lucide icons
  7. LoginView.vue        ← BaseInput + BaseButton + BaseAlert + BaseCard
  8. RegisterView.vue     ← 同上
  9. GuestLoginView.vue   ← 同上，按鈕色改為 secondary variant
  10. NotFoundView.vue    ← Lucide icon + token

第三輪 — 核心功能頁面：
  11. ForumView.vue       ← BaseCard + BaseButton + BaseBadge + BasePagination + 搜尋列響應式
  12. PostDetailView.vue  ← BaseCard + BaseAlert + BaseBadge + BaseModal (report & history)
  13. PostCreateView.vue  ← BaseInput + BaseButton + BaseBadge (keyword tags)
  14. SigsDirectoryView.vue ← BaseCard
  15. SigDetailView.vue   ← BaseCard + BaseTable + BaseBadge + BaseModal + Tab 響應式
  16. FormView.vue        ← BaseCard + BaseAlert + BaseBadge + BaseButton
  17. FormBuilderView.vue ← BaseInput + BaseButton + BaseAlert + BaseCard

第四輪 — 使用者頁面：
  18. ProfileView.vue     ← BaseInput + BaseButton + BaseAlert + BaseCard
  19. NotificationsView.vue ← BaseCard + BasePagination

第五輪 — 管理頁面：
  20. AdminDashboardView.vue ← BaseCard + token
  21. UsersView.vue          ← BaseTable + BaseBadge + BaseModal + BaseButton
  22. ApplicationsView.vue   ← BaseCard + BaseBadge + BaseButton + BaseAlert
  23. ReportsView.vue        ← BaseTable + BaseBadge
  24. AuditLogsView.vue      ← BaseTable + BaseBadge + BasePagination + BaseAlert
  25. InviteCodesView.vue    ← BaseTable + BaseBadge + BaseButton
```

### 階段三：視覺強化 (Visual Enhancement)

在功能性遷移完成後進行的視覺升級：

**3.1 Navbar 毛玻璃效果**
```
backdrop-blur-md bg-surface/80 border-b border-border
```

**3.2 HomeView Hero Section 重塑**

```
未登入首頁結構：
┌─────────────────────────────────────────────────┐
│                                                 │
│      [Inter Bold 2xl/3xl]                       │
│      AI3L Community                             │
│                                                 │
│      [Inter Regular text-muted]                 │
│      AI in Language Learning and Literacy       │
│      Academic Exchange Platform                 │
│                                                 │
│      [BaseButton primary lg] Get Started        │
│      [BaseButton ghost]      Browse as Guest    │
│                                                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────────┐     │
│  │ KeyRound│  │ PenTool │  │ GraduationCap│    │
│  │ Sign In │  │ Register│  │ Explore SIGs │    │
│  │ ...desc │  │ ...desc │  │ ...desc      │    │
│  └─────────┘  └─────────┘  └─────────────┘     │
│                                                 │
└─────────────────────────────────────────────────┘

已登入首頁結構：
┌─────────────────────────────────────────────────┐
│  Welcome back, {displayName}                    │
│                                                 │
│  [BaseButton primary] Browse Forum              │
│  [BaseButton secondary] My SIGs                 │
│                                                 │
│  (Guest warning banner if applicable)           │
└─────────────────────────────────────────────────┘
```

Hero Section 使用 `bg-gradient-to-br from-brand-900 to-brand-700 text-white` 漸層背景。
三張特色卡片各配一個 Lucide icon（`KeyRound`, `PenTool`, `GraduationCap`），使用 `brand-600` 色調。

**3.3 頁面過渡動畫**

在 `App.vue` 的 `<router-view>` 外層加入：
```html
<router-view v-slot="{ Component }">
  <Transition name="page" mode="out-in">
    <component :is="Component" />
  </Transition>
</router-view>
```
```css
.page-enter-active,
.page-leave-active {
  transition: opacity 0.15s ease;
}
.page-enter-from,
.page-leave-to {
  opacity: 0;
}
```

輕量的 fade 效果，不使用 transform 以避免 layout shift。

**3.4 TiptapEditor 工具列升級**

替換工具列按鈕的純文字/符號為 Lucide icons：
- Bold → `Bold`, Italic → `Italic`, Heading → `Heading1` / `Heading2`
- List → `List` / `ListOrdered`, Quote → `Quote`
- Code → `Code`, Link → `Link`, Image → `ImagePlus`
- Undo → `Undo2`, Redo → `Redo2`

### 階段四：全面驗證 (Verification)

詳見第 8 節。

---

## 7. 逐頁改造清單

> 以下為每頁的具體改動項目。標記 `[C]` = 元件替換、`[T]` = Token 遷移、`[R]` = 響應式、`[A]` = 無障礙、`[V]` = 視覺強化。

### AppNavbar.vue
- [C] 角色 Badge → `<BaseBadge>`
- [T] `text-blue-700` → `text-brand-700`；`bg-blue-600` → `bg-brand-600`；所有灰色 → token
- [R] **新增漢堡選單**：`lg:hidden` 漢堡按鈕 + slide-down panel
- [R] 桌面連結群組：`hidden lg:flex lg:items-center lg:gap-4`
- [A] `<nav aria-label="Main navigation">`；漢堡按鈕 `aria-label="Toggle menu"` + `aria-expanded`
- [V] `backdrop-blur-md bg-surface/80`；Lucide `Bell`, `Menu`, `X`, `ChevronDown` icons

### HomeView.vue
- [C] 三張卡片 → `<BaseCard hoverable>` + `<BaseButton>`
- [T] 全部色彩 → token
- [R] 保持現有 `md:grid-cols-3`
- [V] 移除 Emoji → Lucide `KeyRound`, `PenTool`, `GraduationCap`
- [V] Hero Section 漸層背景 + 重新排版

### LoginView.vue
- [C] Card → `<BaseCard>`；Inputs → `<BaseInput>`；Submit → `<BaseButton variant="primary" size="full">`；Error → `<BaseAlert type="error">`
- [T] 全部色彩 → token
- [A] 所有 input 加 `<label>` 關聯

### RegisterView.vue
- [C] 同 LoginView 模式
- [T] 密碼強度指標：`text-green-600` → `text-success-600`；`text-gray-400` → `text-muted`
- [A] 密碼強度清單加 `aria-live="polite"` 即時反饋

### GuestLoginView.vue
- [C] 同 LoginView 模式；Submit → `<BaseButton variant="secondary" size="full">`
- [T] `bg-gray-700` 按鈕改為語義化 secondary variant

### NotFoundView.vue
- [C] Button → `<BaseButton>`
- [T] 色彩 → token
- [V] 替換或保留大字 "404"，可加入 Lucide `FileQuestion` icon

### ForumView.vue
- [C] Post cards → `<BaseCard hoverable>`；Buttons → `<BaseButton>`；Category badge → `<BaseBadge>`；Pagination → `<BasePagination>`
- [T] 全部色彩 → token
- [R] 搜尋/過濾列 → `flex flex-col sm:flex-row sm:items-end gap-3`

### PostDetailView.vue
- [C] Article → `<BaseCard>`；Error → `<BaseAlert>`；Category → `<BaseBadge>`；Report modal → `<BaseModal>`；History modal → `<BaseModal size="xl">`
- [T] 全部色彩 → token
- [A] Modal 加 focus trap + `aria-*`

### PostCreateView.vue
- [C] Inputs → `<BaseInput>` / `<BaseSelect>`；Buttons → `<BaseButton>`；Keyword pills → `<BaseBadge variant="brand">`
- [T] 全部色彩 → token

### SigsDirectoryView.vue
- [C] Cards → `<BaseCard hoverable>`
- [T] 色彩 → token
- [R] 保持現有 `sm:grid-cols-2 lg:grid-cols-3`

### SigDetailView.vue
- [C] Header → `<BaseCard>`；Members → `<BaseTable>`；Role badges → `<BaseBadge>`；Delete modal → `<BaseModal>`；Buttons → `<BaseButton>` (各 variant)
- [T] 全部色彩 → token
- [R] Tab 列加 `overflow-x-auto whitespace-nowrap`

### FormView.vue
- [C] Cards → `<BaseCard>`；Alerts → `<BaseAlert>`；Status badge → `<BaseBadge>`；Buttons → `<BaseButton>`
- [T] `text-red-500` required star → `text-danger-500`
- [A] 每個 question label 與 input 加 `for` / `id` 關聯

### FormBuilderView.vue
- [C] Inputs → `<BaseInput>` / `<BaseSelect>`；Buttons → `<BaseButton>`；Alerts → `<BaseAlert>`
- [T] `border-blue-500` left accent → `border-brand-500`

### ProfileView.vue
- [C] Inputs → `<BaseInput>`；Buttons → `<BaseButton>`；Messages → `<BaseAlert>`
- [T] 全部色彩 → token
- [R] Avatar + form 區域 → `flex flex-col sm:flex-row gap-6`
- [A] Avatar 圖片加 `alt` 屬性

### NotificationsView.vue
- [C] Pagination → `<BasePagination>`
- [T] 全部色彩 → token（`bg-blue-50/40` → `bg-brand-50/40`，`bg-blue-500` dot → `bg-brand-500`）

### AdminDashboardView.vue
- [C] Stat cards → `<BaseCard>`
- [T] 各卡片色彩映射至語義 token
- [R] 保持現有 `sm:grid-cols-2 lg:grid-cols-3`

### UsersView.vue
- [C] Table → `<BaseTable>`；Badges → `<BaseBadge>`；Modals → `<BaseModal>`；Buttons → `<BaseButton>`；Alert → `<BaseAlert>`
- [T] 全部色彩 → token
- [R] 表格外層加 `overflow-x-auto`

### ApplicationsView.vue
- [C] Cards → `<BaseCard>`；Badges → `<BaseBadge>`；Buttons → `<BaseButton>`；Alert → `<BaseAlert>`
- [T] 全部色彩 → token

### ReportsView.vue
- [C] Table → `<BaseTable>`；Badges → `<BaseBadge>`
- [T] 全部色彩 → token
- [R] 表格外層加 `overflow-x-auto`

### AuditLogsView.vue
- [C] Table → `<BaseTable>`；Badge → `<BaseBadge>`；Pagination → `<BasePagination>`；Error → `<BaseAlert>`
- [T] 全部色彩 → token
- [R] 表格外層加 `overflow-x-auto`

### InviteCodesView.vue
- [C] Table → `<BaseTable>`；Badges → `<BaseBadge>`；Button → `<BaseButton>`
- [T] 全部色彩 → token
- [R] 表格外層加 `overflow-x-auto`

### NotificationBell.vue
- [T] 全部色彩 → token
- [V] SVG bell → Lucide `Bell` icon
- [A] Button 加 `aria-label="Notifications"` + `aria-expanded`

### ToastNotification.vue
- [T] 色彩映射改用語義 token
- [A] 加 `role="alert"` + `aria-live="assertive"`

### SkeletonLoader.vue
- [T] `bg-gray-200` → `bg-gray-200`（可保留，skeleton 無需語義化）

### EmptyState.vue
- [T] 色彩 → token
- [V] SVG icon 可選擇替換為 Lucide `Archive` 或 `Inbox`

### PrivacyConsentModal.vue
- [C] Button → `<BaseButton variant="primary" size="full">`
- [T] 全部色彩 → token
- [A] `role="alertdialog"` + `aria-modal="true"` + `aria-labelledby` + `aria-describedby`

### TiptapEditor.vue
- [V] 工具列按鈕替換為 Lucide icons
- [T] `bg-gray-300` active → `bg-brand-100`；`bg-gray-50` toolbar → `bg-surface-alt`

---

## 8. 驗證檢查表

### 8.1 功能驗證
- [ ] 所有頁面可正常瀏覽，無 console error
- [ ] 所有表單可正常提交（Login / Register / Guest / Profile / PostCreate / FormBuilder / FormView）
- [ ] 所有 Modal 可正常開關（Report / History / Ban / Create Account / Delete SIG）
- [ ] Toast 通知正常顯示四種狀態
- [ ] WebSocket 通知正常接收
- [ ] 分頁在所有使用處正常運作
- [ ] 角色 Badge 色彩在所有頁面一致

### 8.2 響應式驗證
- [ ] Navbar 在 < 1024px 顯示漢堡選單，≥ 1024px 顯示橫向連結
- [ ] 漢堡選單展開/收合動畫流暢
- [ ] Admin 表格在手機上可水平捲動
- [ ] ForumView 搜尋列在手機上堆疊排列
- [ ] 所有頁面在 375px 寬度下無水平溢出
- [ ] 所有頁面在 1920px 寬度下佈局合理

### 8.3 無障礙驗證
- [ ] 所有互動元素可透過 Tab 到達
- [ ] Modal focus trap 正常運作
- [ ] Escape 鍵可關閉所有 Modal 和 Dropdown
- [ ] 使用螢幕閱讀器測試主要流程（登入 → 瀏覽論壇 → 發文）

### 8.4 效能驗證
- [ ] Network tab 無任何外部 CDN 請求（`fonts.googleapis.com` 等）
- [ ] Vite build 後 Lucide icons 有 tree-shaking 效果（僅打包使用的 icon）
- [ ] Inter Variable 字體檔 `.woff2` 正確出現在 `dist/assets/`
- [ ] 總字體載入 < 100KB (Inter Variable woff2 約 ~90KB)

### 8.5 設計一致性驗證
- [ ] 全站無任何硬編碼 `blue-600`, `red-50` 等 Tailwind 原始色（僅 `orange-*`, `purple-*` 角色色除外）
- [ ] 所有按鈕尺寸統一（同場景下的按鈕使用相同 size prop）
- [ ] 所有 Input focus 狀態一致
- [ ] 所有 Modal overlay 一致使用 `bg-black/40`

---

## 附錄：檔案清單總覽

```
施工涉及的檔案（共 ~35 個）：

新增：
  src/components/base/BaseButton.vue
  src/components/base/BaseInput.vue
  src/components/base/BaseSelect.vue
  src/components/base/BaseTextarea.vue
  src/components/base/BaseCard.vue
  src/components/base/BaseAlert.vue
  src/components/base/BaseBadge.vue
  src/components/base/BaseModal.vue
  src/components/base/BaseTable.vue
  src/components/base/BasePagination.vue

修改：
  src/style.css                              ← Design Token
  src/main.ts                                ← Font import
  src/App.vue                                ← Layout wrapper + page transition
  src/components/AppNavbar.vue               ← 響應式漢堡選單 + 全面重構
  src/components/NotificationBell.vue        ← Token + Lucide
  src/components/ToastNotification.vue       ← Token + a11y
  src/components/SkeletonLoader.vue          ← Token
  src/components/EmptyState.vue              ← Token + Lucide
  src/components/TiptapEditor.vue            ← Lucide toolbar icons
  src/components/PrivacyConsentModal.vue     ← BaseButton + Token + a11y
  src/views/HomeView.vue                     ← Hero Section 全面重塑
  src/views/LoginView.vue                    ← Base 元件替換
  src/views/RegisterView.vue                 ← Base 元件替換
  src/views/GuestLoginView.vue               ← Base 元件替換
  src/views/NotFoundView.vue                 ← Token + Lucide
  src/views/ProfileView.vue                  ← Base 元件替換 + 響應式
  src/views/NotificationsView.vue            ← Token + BasePagination
  src/views/forum/ForumView.vue              ← Base 元件替換 + 搜尋列響應式
  src/views/forum/PostDetailView.vue         ← Base 元件 + BaseModal
  src/views/forum/PostCreateView.vue         ← Base 元件替換
  src/views/sigs/SigsDirectoryView.vue       ← BaseCard
  src/views/sigs/SigDetailView.vue           ← 全面重構（Tab + Table + Modal）
  src/views/forms/FormView.vue               ← Base 元件替換
  src/views/forms/FormBuilderView.vue        ← Base 元件替換
  src/views/admin/AdminDashboardView.vue     ← BaseCard + Token
  src/views/admin/UsersView.vue              ← BaseTable + BaseModal 全面重構
  src/views/admin/ApplicationsView.vue       ← Base 元件替換
  src/views/admin/ReportsView.vue            ← BaseTable + Token
  src/views/admin/AuditLogsView.vue          ← BaseTable + BasePagination
  src/views/admin/InviteCodesView.vue        ← BaseTable + Token
```
