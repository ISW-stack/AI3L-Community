#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# init-letsencrypt.sh — Initial Let's Encrypt certificate issuance
#
# Usage:  ./scripts/init-letsencrypt.sh your-domain.com [email@example.com]
#
# Prerequisites:
#   - Docker and docker compose installed
#   - Nginx container running with port 80 reachable
#   - DNS A record pointing to this server
# ──────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="${1:?Usage: $0 <domain> [email]}"
EMAIL="${2:-}"

SSL_DIR="./nginx/ssl"
WEBROOT_DIR="./certbot-webroot"

mkdir -p "$SSL_DIR" "$WEBROOT_DIR"

echo "==> Requesting certificate for $DOMAIN ..."

CERTBOT_ARGS=(
  certonly
  --webroot
  -w /var/www/certbot
  -d "$DOMAIN"
  --agree-tos
  --no-eff-email
  --non-interactive
)

if [ -n "$EMAIL" ]; then
  CERTBOT_ARGS+=(--email "$EMAIL")
else
  CERTBOT_ARGS+=(--register-unsafely-without-email)
fi

docker run --rm \
  -v "$SSL_DIR:/etc/letsencrypt" \
  -v "$WEBROOT_DIR:/var/www/certbot" \
  certbot/certbot "${CERTBOT_ARGS[@]}"

echo ""
echo "==> Certificate obtained successfully!"
echo "    Certificates written to: $SSL_DIR"
echo ""
echo "Next steps:"
echo "  1. Copy live certs to the expected paths:"
echo "     cp $SSL_DIR/live/$DOMAIN/fullchain.pem $SSL_DIR/fullchain.pem"
echo "     cp $SSL_DIR/live/$DOMAIN/privkey.pem   $SSL_DIR/privkey.pem"
echo "  2. Uncomment the HTTPS server block in nginx/conf.d/default.conf"
echo "  3. Replace YOUR_DOMAIN with $DOMAIN"
echo "  4. Restart nginx: docker compose restart nginx"
echo "  5. Set up auto-renewal: see scripts/renew-certs.sh"
