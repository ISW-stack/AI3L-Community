#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# renew-certs.sh — Renew Let's Encrypt certificates + reload nginx
#
# Add to crontab (runs every 60 days at 03:00):
#   0 3 */60 * * /path/to/scripts/renew-certs.sh >> /var/log/certbot-renew.log 2>&1
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SSL_DIR="./nginx/ssl"
WEBROOT_DIR="./certbot-webroot"

echo "[$(date)] Starting certificate renewal ..."

docker run --rm \
  -v "$SSL_DIR:/etc/letsencrypt" \
  -v "$WEBROOT_DIR:/var/www/certbot" \
  certbot/certbot renew --quiet

echo "[$(date)] Renewal complete. Reloading nginx ..."

docker compose exec nginx nginx -s reload

echo "[$(date)] Done."
