#!/bin/bash
# ==========================================================================
# AI3L Community — Automated Backup Script
#
# Backs up PostgreSQL + R2 attachments to Hetzner Storage Box via rsync/rclone.
#
# Prerequisites:
#   1. SSH key configured for Hetzner Storage Box:
#      ssh-keygen -t ed25519 -f ~/.ssh/hetzner_storagebox
#      ssh-copy-id -p 23 -i ~/.ssh/hetzner_storagebox u123456@u123456.your-storagebox.de
#   2. rclone configured with R2 remote:
#      rclone config  →  name: r2  →  type: s3  →  provider: Cloudflare
#   3. Environment variables set (or source from .env)
#
# Usage:
#   ./scripts/backup.sh           # Full backup (DB + R2)
#   ./scripts/backup.sh db        # Database only
#   ./scripts/backup.sh r2        # R2 files only
#
# Crontab example (daily DB at 3am, weekly R2 on Sunday at 4am):
#   0 3 * * * /opt/ai3l/scripts/backup.sh db >> /var/log/ai3l-backup.log 2>&1
#   0 4 * * 0 /opt/ai3l/scripts/backup.sh r2 >> /var/log/ai3l-backup.log 2>&1
# ==========================================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source .env if it exists
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_DIR/.env"
    set +a
fi

# Backup settings
BACKUP_DIR="${BACKUP_DIR:-/tmp/ai3l-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

# Hetzner Storage Box
HETZNER_USER="${HETZNER_USER:?Set HETZNER_USER (e.g. u123456)}"
HETZNER_HOST="${HETZNER_HOST:-${HETZNER_USER}.your-storagebox.de}"
HETZNER_SSH_KEY="${HETZNER_SSH_KEY:-$HOME/.ssh/hetzner_storagebox}"
HETZNER_PATH="${HETZNER_PATH:-./ai3l-backup}"

# PostgreSQL (from .env)
PG_USER="${POSTGRES_USER:-ai3l}"
PG_DB="${POSTGRES_DB:-ai3l_community}"

# R2 rclone remote name
R2_REMOTE="${R2_REMOTE:-r2}"
R2_BUCKET="${S3_BUCKET_NAME:-ai3l-uploads}"

# ── Helpers ───────────────────────────────────────────────────────────────
timestamp() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(timestamp)] $*"; }

# Restrict permissions on backup files (owner-only)
umask 077
mkdir -p "$BACKUP_DIR"

# ── Database Backup ───────────────────────────────────────────────────────
backup_db() {
    local dump_file="$BACKUP_DIR/db-$(date +%F_%H%M).sql.gz"
    log "Starting PostgreSQL backup..."

    docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" exec -T postgres \
        pg_dump -U "$PG_USER" -d "$PG_DB" --no-owner --no-acl | gzip > "$dump_file"

    local size
    size=$(du -h "$dump_file" | cut -f1)
    log "Database dump complete: $dump_file ($size)"

    # Upload to Hetzner
    log "Uploading to Hetzner Storage Box..."
    rsync -avz --progress \
        -e "ssh -p 23 -i $HETZNER_SSH_KEY -o StrictHostKeyChecking=accept-new" \
        "$dump_file" \
        "${HETZNER_USER}@${HETZNER_HOST}:${HETZNER_PATH}/db/"

    log "Database backup uploaded successfully"
}

# ── R2 File Backup ────────────────────────────────────────────────────────
backup_r2() {
    log "Starting R2 file sync to Hetzner (direct rclone → SFTP)..."

    # Direct sync: R2 → Hetzner Storage Box via SFTP (no local staging needed)
    # Requires rclone remote "hetzner" configured as SFTP:
    #   rclone config → name: hetzner → type: sftp → host: $HETZNER_HOST → port: 23
    #                  → user: $HETZNER_USER → key_file: $HETZNER_SSH_KEY
    rclone sync "${R2_REMOTE}:${R2_BUCKET}" \
        "hetzner:${HETZNER_PATH}/r2-files/" \
        --transfers=4 \
        --checkers=8 \
        --fast-list \
        --stats-one-line \
        -v

    log "R2 file sync complete"
}

# ── Local Cleanup ─────────────────────────────────────────────────────────
cleanup_local() {
    log "Cleaning up local backups older than ${RETENTION_DAYS} days..."
    find "$BACKUP_DIR" -name "db-*.sql.gz" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
    log "Local cleanup complete"
}

# ── Main ──────────────────────────────────────────────────────────────────
MODE="${1:-all}"

log "=== AI3L Backup Started (mode: $MODE) ==="

case "$MODE" in
    db)
        backup_db
        ;;
    r2)
        backup_r2
        ;;
    all)
        backup_db
        backup_r2
        ;;
    *)
        echo "Usage: $0 [db|r2|all]"
        exit 1
        ;;
esac

cleanup_local
log "=== AI3L Backup Complete ==="
