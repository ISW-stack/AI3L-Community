#!/bin/sh
set -e

# ── Always generate security-headers.conf from template ──────────
# If STORAGE_CSP_ORIGIN is not set, the variable expands to empty string,
# which is safe — the CSP will simply omit the external storage origin.
export STORAGE_CSP_ORIGIN="${STORAGE_CSP_ORIGIN:-}"
envsubst '$STORAGE_CSP_ORIGIN' \
    < /etc/nginx/snippets/security-headers.conf.template \
    > /etc/nginx/snippets/security-headers.conf
echo "[entrypoint] security-headers.conf generated (STORAGE_CSP_ORIGIN=${STORAGE_CSP_ORIGIN:-<not set>})"

# ── Enable HTTPS if TLS certificates exist ────────────────────────
CERT_PATH="/etc/nginx/ssl/fullchain.pem"
KEY_PATH="/etc/nginx/ssl/privkey.pem"

if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ]; then
    echo "[entrypoint] TLS certificates found — enabling HTTPS server block"
    # Only uncomment lines that start with '#HTTPS ' (safe prefix marker)
    # This avoids uncommenting documentation comments
    sed -i 's/^#HTTPS //' /etc/nginx/conf.d/default.conf
else
    echo "[entrypoint] No TLS certificates found — running HTTP only (dev mode)"
fi

exec nginx -g 'daemon off;'
