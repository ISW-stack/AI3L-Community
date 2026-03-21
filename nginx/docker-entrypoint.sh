#!/bin/sh
set -e

# ── Process security-headers template if MINIO_CSP_ORIGIN is set ──
if [ -n "$MINIO_CSP_ORIGIN" ]; then
    envsubst '$MINIO_CSP_ORIGIN' \
        < /etc/nginx/snippets/security-headers.conf.template \
        > /etc/nginx/snippets/security-headers.conf
    echo "[entrypoint] security-headers.conf generated with MINIO_CSP_ORIGIN=$MINIO_CSP_ORIGIN"
fi

# ── Enable HTTPS if TLS certificates exist ────────────────────────
CERT_PATH="/etc/nginx/ssl/fullchain.pem"
KEY_PATH="/etc/nginx/ssl/privkey.pem"

if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ]; then
    echo "[entrypoint] TLS certificates found — enabling HTTPS server block"
    # Uncomment the HTTPS server blocks in default.conf
    sed -i 's/^# \(.*\)/\1/' /etc/nginx/conf.d/default.conf
    # Comment out the dev HTTP server block (listen 80 with server_name _)
    # The HTTPS block includes its own HTTP→HTTPS redirect
else
    echo "[entrypoint] No TLS certificates found — running HTTP only (dev mode)"
fi

exec nginx -g 'daemon off;'
