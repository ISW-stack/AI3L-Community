# AI3L Community — Production 部署計畫

> 文件日期：2026-03-26
> 目標環境：Hetzner CPX32（新加坡）+ Cloudflare R2 + Cloudflare Free CDN

---

## 一、目標架構

```
使用者瀏覽器
     │ HTTPS
     ▼
Cloudflare CDN（SSL termination + DDoS 防護）
     │ HTTPS（Full Strict）
     ▼
Hetzner CPX32 — nginx（443）
     ├──► /api/*  ──► FastAPI（port 8000）
     │                    │
     │             ┌──────┼──────┐
     │          postgres  redis  celery
     │
     └──► /*  ──► nginx 靜態檔案（Vue SPA）
                      │
                  Cloudflare R2（檔案上傳/下載）
```

**核心決策：**
- 不使用 MinIO 容器 → 改用 Cloudflare R2（S3 相容 API，零 egress 費用）
- Cloudflare 做 SSL termination，nginx 仍需 443（Full Strict 模式）
- 前端透過 GitHub Actions 自動 build 並部署至 server

---

## 二、硬體資源評估

### Hetzner CPX32（4 vCPU / 8 GB RAM / 160 GB SSD）

| 服務 | CPU limit | RAM limit | 實際估計 |
|------|-----------|-----------|---------|
| nginx | 0.5 | 256 MB | ~30 MB |
| fastapi (gunicorn 4 workers) | 2.0 | 2 GB | ~600 MB |
| postgres | 2.0 | 3 GB | ~800 MB（shared_buffers=2GB 含 OS cache） |
| redis | 0.5 | 512 MB | ~256 MB（maxmemory 限制） |
| celery worker | 1.0 | 768 MB | ~300 MB |
| celery-beat | 0.25 | 128 MB | ~80 MB |
| OS + Docker overhead | — | ~1 GB | — |
| **合計 limit** | **6.25\*** | **6.6 GB** | **~2 GB** |

> \* Docker CPU limits 為軟性限制，不是硬性排程保留。超過物理核心數無妨，各服務不會同時跑滿。
>
> **結論：** RAM 充裕，CPU 初期夠用。若 FastAPI 流量增大，可調低 `PG_SHARED_BUFFERS` 或 postgres 的 limit。

---

## 三、SSL / TLS 策略

### 建議方案：Cloudflare Full (Strict) + Origin Certificate

**不建議**使用 Let's Encrypt certbot（docker-compose.prod.yml 現有 certbot service）的原因：
- 與 Cloudflare 合用時，Cloudflare 已擋在前面，Let's Encrypt HTTP challenge 無法正常運作（需要 DNS challenge）。
- Cloudflare Origin Certificate 免費、有效期 15 年、自動信任 Cloudflare → Server 這段。

### 設定步驟

1. 在 Cloudflare Dashboard → SSL/TLS → 選 **Full (strict)**
2. Origin Certificates → 建立新憑證 → 選你的 domain → 下載 `.pem` 和 `.key`
3. 上傳至 server：

```bash
scp cloudflare-origin.pem root@<server-ip>:/path/to/ai3l-community/nginx/ssl/cert.pem
scp cloudflare-origin.key root@<server-ip>:/path/to/ai3l-community/nginx/ssl/key.pem
```

4. `nginx/conf.d/default.conf` 的 HTTPS server block 使用這兩個檔案。

> nginx port 443 保留（prod compose 已設定），certbot service 設為 profile-only，不影響主要啟動。

---

## 四、Cloudflare R2 設定

R2 **只用來存放檔案**，瀏覽器透過後端產生的 presigned URL 直接存取，不需要自訂 domain、不需要開 public access。

### 前置作業（Cloudflare Dashboard）

1. 建立 R2 bucket：`ai3l-community`，設定為 **Private**
2. 建立 R2 API Token（Custom Token）：
   - 權限：`Object Read & Write` on bucket `ai3l-community`
   - 記錄 `Access Key ID` 和 `Secret Access Key`

### .env 對應設定

```bash
# 移除舊 MinIO 相關設定：
# MINIO_ROOT_USER=...
# MINIO_ROOT_PASSWORD=...

# 新增 R2 設定：
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=<r2_access_key_id>
S3_SECRET_ACCESS_KEY=<r2_secret_key>
S3_BUCKET_NAME=ai3l-community
S3_REGION=auto

# presigned URL base（與 endpoint 相同，R2 預設 endpoint 瀏覽器可直接訪問）
MINIO_PUBLIC_URL=https://<account-id>.r2.cloudflarestorage.com

# nginx CSP 允許瀏覽器載入來自 R2 的資源
STORAGE_CSP_ORIGIN=https://<account-id>.r2.cloudflarestorage.com
```

### 運作原理

瀏覽器不會直接訪問 R2 bucket，而是後端產生帶簽名的臨時 URL（presigned URL），
瀏覽器用這個 URL 直接向 R2 下載/上傳。Bucket 保持 Private，presigned URL 本身帶有驗證資訊，R2 會接受。

### 驗證 R2 相容性

程式碼已使用 boto3/aioboto3 的 S3 API，R2 完全相容，不需要改程式碼。
`generate_presigned_url()` 在 `app/core/storage.py` 中的 `MINIO_PUBLIC_URL` 替換邏輯，
確保 endpoint URL 和 `MINIO_PUBLIC_URL` 設成一樣的值即可。

---

## 五、伺服器初始設定（一次性）

```bash
# 1. 連線進 Hetzner server
ssh root@<server-ip>

# 2. 安裝 Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# 3. Clone repo（不要透過 OneDrive）
git clone https://github.com/Isaries/AI3L-Community.git /opt/ai3l-community
cd /opt/ai3l-community

# 4. 建立 .env（直接在 server 上建，不要從 Windows 複製）
cp .env.production.example .env
nano .env   # 填入所有 secrets
```

> **重要：** `.env` 只存在 server 上，不要進 git、不要放 OneDrive。
> 這解決了 INFRA-19（生產 secrets 在 OneDrive 的風險）。

---

## 六、前端部署流程

### 推薦方案：GitHub Actions 自動部署

建立 `.github/workflows/deploy.yml`：

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Build frontend
        working-directory: frontend
        run: |
          npm ci
          npm run build
        env:
          VITE_API_BASE_URL: https://${{ secrets.SERVER_DOMAIN }}

      - name: Deploy to server
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          source: "frontend/dist/*"
          target: "/opt/ai3l-community/nginx/html"
          strip_components: 2

      - name: Reload nginx
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: docker compose -f /opt/ai3l-community/docker-compose.prod.yml exec nginx nginx -s reload
```

**GitHub Secrets 需設定：**
- `SERVER_HOST` — server IP
- `SERVER_USER` — 登入帳號（建議建立 `deploy` 用戶）
- `SSH_PRIVATE_KEY` — deploy 用戶的 SSH private key
- `SERVER_DOMAIN` — 你的 domain（用於 Vite build）

### 備用方案：手動部署 SOP

若不用 CI/CD，每次更新前端時在 dev 機器執行：

```bash
cd frontend
npm run build
rsync -avz --delete dist/ root@<server-ip>:/opt/ai3l-community/nginx/html/
ssh root@<server-ip> "docker compose -f /opt/ai3l-community/docker-compose.prod.yml exec nginx nginx -s reload"
```

---

## 七、首次啟動步驟

```bash
cd /opt/ai3l-community

# 1. 確認 .env 填寫完畢
grep "changeme" .env  # 輸出不應該有任何結果

# 2. 放置 Cloudflare Origin Certificate
# （見第三節 SSL 設定步驟）

# 3. 確認 nginx/html/ 有前端 build 產物
ls nginx/html/index.html

# 4. 啟動所有服務
docker compose -f docker-compose.prod.yml up -d

# 5. 查看 migrate 是否成功
docker compose -f docker-compose.prod.yml logs migrate

# 6. 確認所有服務健康
docker compose -f docker-compose.prod.yml ps
```

---

## 八、資料庫備份策略

### 每日自動備份

在 server 上建立備份腳本並加入 crontab：

```bash
# /opt/ai3l-community/scripts/backup-db.sh 已存在，直接排程：
crontab -e

# 每天凌晨 3 點備份，保留 30 天
0 3 * * * /opt/ai3l-community/scripts/backup-db.sh >> /var/log/ai3l-backup.log 2>&1
```

備份檔案存在 `./backups/`，Hetzner SSD 160 GB 有充裕空間。

### 異地備份（強烈建議）

將備份 `.sql.gz` 定期同步到 R2 或 Hetzner 另一個節點：

```bash
# 每週日推一次到 R2（使用 rclone）
0 4 * * 0 rclone copy /opt/ai3l-community/backups/ r2:ai3l-backups/db/
```

---

## 九、監控與告警

### 基本監控（免費方案）

1. **Hetzner 內建監控**：CPU、RAM、網路圖表，可設 email 告警
2. **Cloudflare Analytics**：流量、錯誤率、快取命中率
3. **UptimeRobot**（免費）：每 5 分鐘 ping `https://your-domain.com/api/v1/health/live`，down 時發 email

### 進階（選配）

- Datadog：`docker-compose.prod.yml` 已內建 `datadog-agent` service（需 `--profile monitoring` 啟動）
- Sentry：設 `SENTRY_DSN` 環境變數，FastAPI 自動上報 exception

---

## 十、nginx 設定注意事項

### Cloudflare IP 白名單

`nginx/conf.d/default.conf` 已有 `set_real_ip_from` Cloudflare IP 段，確認包含最新清單：

```nginx
# 定期更新 Cloudflare IP 清單：
# https://www.cloudflare.com/ips-v4
# https://www.cloudflare.com/ips-v6
```

### 建議在 Cloudflare 啟用的功能

| 功能 | 設定位置 | 建議值 |
|------|---------|--------|
| SSL 模式 | SSL/TLS → Overview | Full (strict) |
| HSTS | SSL/TLS → Edge Certs | 啟用，max-age=31536000 |
| Bot Fight Mode | Security → Bots | 啟用 |
| Browser Integrity Check | Security → Settings | 啟用 |
| 快取靜態資源 | Caching → Configuration | Standard |

> nginx 已自行設定 HSTS header，Cloudflare 這邊設定的是 edge 層 HSTS，兩者相輔相成，不衝突。

---

## 十一、上線前 Checklist

### 環境設定
- [ ] `.env` 所有 `changeme_*` 已替換為強隨機 secrets
- [ ] `FASTAPI_ENV=production`、`FASTAPI_DEBUG=false`
- [ ] `CORS_ORIGINS=https://your-domain.com`（不含 localhost）
- [ ] `COOKIE_SECURE=true`、`COOKIE_DOMAIN=your-domain.com`
- [ ] `SERVER_DOMAIN=your-domain.com`
- [ ] `S3_ENDPOINT_URL`、`S3_ACCESS_KEY_ID`、`S3_SECRET_ACCESS_KEY`、`S3_BUCKET_NAME` 已設定（R2）
- [ ] `MINIO_PUBLIC_URL` 指向 R2 的公開 URL（瀏覽器可訪問）
- [ ] `STORAGE_CSP_ORIGIN` 與 `MINIO_PUBLIC_URL` 一致
- [ ] `SENTRY_DSN` 設定（選配但建議）

### SSL / 網路
- [ ] Cloudflare SSL 模式設為 Full (strict)
- [ ] Cloudflare Origin Certificate 已放至 `nginx/ssl/`
- [ ] `nginx/conf.d/default.conf` 的 HTTPS server block 已啟用
- [ ] Cloudflare HSTS 啟用
- [ ] 從外部測試 `https://your-domain.com` 回傳 200

### 資料與備份
- [ ] `migrate` service 執行成功（alembic upgrade head + check）
- [ ] R2 bucket 存取測試：上傳一個測試檔案並確認 presigned URL 可用
- [ ] crontab 備份排程已設定
- [ ] 執行一次手動備份並確認 `.sql.gz` 可成功還原

### 功能驗證
- [ ] 登入、登出正常
- [ ] 檔案上傳後在瀏覽器可顯示（avatar、附件）
- [ ] WebSocket 連線正常（通知、DM）
- [ ] Celery Beat 任務正在執行（`docker compose logs celery-beat`）

### 安全
- [ ] `GET /api/v1/health` 需要 SUPER_ADMIN（直接訪問返回 401）
- [ ] `GET /api/v1/health/live` 公開（返回 200）
- [ ] 從 Cloudflare 以外的 IP 直接連 server port 80/443 時，建議用 Hetzner Firewall 封鎖

---

## 十二、已知問題與限制

| 項目 | 說明 | 建議處理方式 |
|------|------|------------|
| certbot service | prod compose 保留了 certbot，但與 Cloudflare Origin Cert 方案衝突 | 忽略不啟動即可（profile: certbot 不會自動跑）|
| 手動前端部署風險 | 忘記 build 或 rsync 錯誤會導致版本不一致 | 改用 GitHub Actions（見第六節）|
| CPU limits 超過物理核心 | 合計 limit 6.25 vCPU > 4 vCPU | Docker limits 為軟性限制，不影響運作；高峰期監控 CPU 使用率 |
| Redis maxmemory | prod compose limit 512 MB，redis-prod.conf 應確認 `maxmemory 256mb` | 若快取命中率低，考慮提高到 384 MB |
| DB 單點 | PostgreSQL 無 replica，單點故障時服務中斷 | 學術社群可接受；日後可考慮 Hetzner Managed Database |
| .env 管理 | 沒有 secret manager，純靠 SSH 訪問保護 | 可考慮 Bitwarden Secrets Manager 或 Doppler（免費方案）|
