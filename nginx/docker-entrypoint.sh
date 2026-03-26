#!/bin/sh
set -e

# ── Generate security-headers.conf from template (if template exists) ──
# In dev Docker Compose the final .conf is volume-mounted directly,
# so the .template file may not be present — skip envsubst in that case.
export STORAGE_CSP_ORIGIN="${STORAGE_CSP_ORIGIN:-}"
if [ -f /etc/nginx/snippets/security-headers.conf.template ]; then
    envsubst '$STORAGE_CSP_ORIGIN' \
        < /etc/nginx/snippets/security-headers.conf.template \
        > /etc/nginx/snippets/security-headers.conf
    echo "[entrypoint] security-headers.conf generated (STORAGE_CSP_ORIGIN=${STORAGE_CSP_ORIGIN:-<not set>})"
else
    echo "[entrypoint] security-headers.conf.template not found — using mounted conf as-is"
fi

# ── Substitute domain placeholder in nginx config ─────────────────
# Work on a copy so host-mounted source files are never modified in-place
if [ -f /etc/nginx/conf.d/default.conf.template ]; then
    cp /etc/nginx/conf.d/default.conf.template /etc/nginx/conf.d/default.conf
elif [ -f /etc/nginx/conf.d/default.conf ]; then
    # First run: create template from original for future restarts
    cp /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.template
fi

if [ -n "${SERVER_DOMAIN:-}" ] && [ "$SERVER_DOMAIN" != "_" ]; then
    sed -i "s/YOUR_DOMAIN/${SERVER_DOMAIN}/g" /etc/nginx/conf.d/default.conf
    # Abort if substitution failed (YOUR_DOMAIN still present)
    if grep -q 'YOUR_DOMAIN' /etc/nginx/conf.d/default.conf; then
        echo "[entrypoint] ERROR: YOUR_DOMAIN placeholder still present after substitution — aborting"
        exit 1
    fi
    echo "[entrypoint] server_name set to ${SERVER_DOMAIN}"
else
    # In production (TLS certs present), SERVER_DOMAIN must be set
    if [ -f "/etc/nginx/ssl/fullchain.pem" ]; then
        echo "[entrypoint] ERROR: SERVER_DOMAIN is required for production (TLS mode) — aborting"
        exit 1
    fi
    echo "[entrypoint] SERVER_DOMAIN not set — YOUR_DOMAIN placeholder unchanged (dev mode)"
fi

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
