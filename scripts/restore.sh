#!/usr/bin/env bash
# Restore PostgreSQL from a backup file (local or R2)
# Usage:
#   ./restore.sh /path/to/ojik_bms_20260327_030000.sql.gz   # from local file
#   ./restore.sh r2:ojik-bms-backups/daily/ojik_bms_20260327_030000.sql.gz  # from R2
set -euo pipefail

APP_DIR="/opt/ojik-bms"
set -a; source "$APP_DIR/.env.prod"; set +a

BACKUP_SRC="${1:?Usage: $0 <backup_file_or_r2_path>}"
LOCAL_FILE="/tmp/restore_target.sql.gz"

if [[ "$BACKUP_SRC" == r2:* ]]; then
    echo "Downloading from R2..."
    rclone copy "$BACKUP_SRC" /tmp/ \
        --s3-access-key-id "$R2_ACCESS_KEY_ID" \
        --s3-secret-access-key "$R2_SECRET_ACCESS_KEY" \
        --s3-endpoint "$R2_ENDPOINT"
    LOCAL_FILE="/tmp/$(basename "$BACKUP_SRC")"
else
    LOCAL_FILE="$BACKUP_SRC"
fi

echo "WARNING: This will DROP and RECREATE the database '$POSTGRES_DB'."
read -r -p "Type 'yes' to continue: " CONFIRM
[[ "$CONFIRM" == "yes" ]] || { echo "Aborted."; exit 1; }

echo "Stopping API, celery services..."
docker compose -f "$APP_DIR/docker-compose.prod.yml" stop api celery celery-beat

echo "Restoring database..."
gunzip -c "$LOCAL_FILE" | docker compose -f "$APP_DIR/docker-compose.prod.yml" exec -T postgres \
    psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB; CREATE DATABASE $POSTGRES_DB;" 2>/dev/null || true

gunzip -c "$LOCAL_FILE" | docker compose -f "$APP_DIR/docker-compose.prod.yml" exec -T postgres \
    psql -U "$POSTGRES_USER" "$POSTGRES_DB"

echo "Restarting services..."
docker compose -f "$APP_DIR/docker-compose.prod.yml" up -d

echo "Restore complete."
