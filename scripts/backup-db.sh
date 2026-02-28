#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# backup-db.sh — Automated PostgreSQL backup via Docker Compose
#
# Usage:  ./scripts/backup-db.sh
#
# - Dumps the database from the running postgres container
# - Compresses with gzip and saves to ./backups/
# - Retains the last 30 backups (deletes older files)
#
# Crontab example (daily at 03:00):
#   0 3 * * * cd /path/to/project && ./scripts/backup-db.sh >> /var/log/db-backup.log 2>&1
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# Load environment variables
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-ai3l}"
POSTGRES_DB="${POSTGRES_DB:-ai3l_community}"
BACKUP_DIR="./backups"
RETAIN_COUNT=30

TIMESTAMP="$(date +%Y-%m-%d_%H%M%S)"
FILENAME="ai3l_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup: $FILENAME ..."

docker compose exec -T postgres pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --no-owner \
  --no-privileges \
  --format=plain \
  | gzip > "${BACKUP_DIR}/${FILENAME}"

FILE_SIZE=$(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1)
echo "[$(date)] Backup complete: ${BACKUP_DIR}/${FILENAME} (${FILE_SIZE})"

# Retain only the last N backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/ai3l_*.sql.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$RETAIN_COUNT" ]; then
  DELETE_COUNT=$((BACKUP_COUNT - RETAIN_COUNT))
  echo "[$(date)] Removing $DELETE_COUNT old backup(s) ..."
  ls -1t "$BACKUP_DIR"/ai3l_*.sql.gz | tail -n "$DELETE_COUNT" | xargs rm -f
fi

echo "[$(date)] Done. ($BACKUP_COUNT backup(s) on disk)"
