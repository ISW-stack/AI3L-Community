#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# restore-db.sh — Restore PostgreSQL from a gzipped backup
#
# Usage:  ./scripts/restore-db.sh backups/ai3l_2026-02-28_030000.sql.gz
# ──────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_FILE="${1:?Usage: $0 <backup-file.sql.gz>}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: File not found: $BACKUP_FILE"
  exit 1
fi

# Load environment variables
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-ai3l}"
POSTGRES_DB="${POSTGRES_DB:-ai3l_community}"

echo "==> WARNING: This will DROP and re-create the database '$POSTGRES_DB'."
echo "    Backup file: $BACKUP_FILE"
read -rp "    Continue? [y/N] " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo "[$(date)] Dropping and re-creating database ..."
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid();
  DROP DATABASE IF EXISTS \"$POSTGRES_DB\";
  CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";
"

echo "[$(date)] Restoring from $BACKUP_FILE ..."
gunzip -c "$BACKUP_FILE" | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" --quiet

echo "[$(date)] Restore complete."
