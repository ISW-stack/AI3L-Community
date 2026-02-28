#!/bin/bash
# Initialize MinIO buckets for AI3L Community
# Usage: Run this script after MinIO container is healthy
#   docker compose exec minio sh -c "$(cat scripts/init-minio.sh)"
# Or run with mc CLI from host:
#   mc alias set ai3l http://localhost:9000 minioadmin changeme_minio
#   ./scripts/init-minio.sh

set -euo pipefail

MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-changeme_minio}"
BUCKET_NAME="${MINIO_BUCKET_NAME:-ai3l-uploads}"

echo "Configuring MinIO alias..."
mc alias set ai3l "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

echo "Creating bucket: $BUCKET_NAME"
mc mb "ai3l/$BUCKET_NAME" --ignore-existing

echo "Setting bucket policy to private..."
mc anonymous set none "ai3l/$BUCKET_NAME"

echo "MinIO initialization complete."
echo "  Endpoint: $MINIO_ENDPOINT"
echo "  Bucket:   $BUCKET_NAME"
