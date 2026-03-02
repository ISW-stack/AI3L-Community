#!/usr/bin/env bash
# Build the frontend and sync the output to nginx/html/.
# Run from the project root: bash scripts/build-frontend.sh
# Pass --restart to also restart the nginx container after copying.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
NGINX_HTML_DIR="$ROOT_DIR/nginx/html"

RESTART_NGINX=false
for arg in "$@"; do
  [[ "$arg" == "--restart" ]] && RESTART_NGINX=true
done

echo "==> Building frontend..."
cd "$FRONTEND_DIR"
npm run build

echo "==> Clearing old assets..."
rm -rf "$NGINX_HTML_DIR/assets"

echo "==> Copying new build to nginx/html/..."
cp -r dist/* "$NGINX_HTML_DIR/"

echo "==> Build complete. Files in nginx/html/:"
ls "$NGINX_HTML_DIR"

if $RESTART_NGINX; then
  echo "==> Restarting nginx container..."
  cd "$ROOT_DIR"
  docker compose restart nginx
  echo "==> nginx restarted."
fi

echo ""
echo "Done. Visit http://localhost:3000 to see the latest frontend."
