#!/usr/bin/env bash
# Daily PostgreSQL backup → Cloudflare R2
# Prerequisites: rclone configured with an R2 remote named "r2"
# Cron example (daily 3 AM): 0 3 * * * /opt/ojik-bms/scripts/backup.sh >> /var/log/ojik-backup.log 2>&1
set -euo pipefail

APP_DIR="/opt/ojik-bms"
BACKUP_DIR="/tmp/ojik-backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="ojik_bms_${DATE}.sql.gz"

# Load env so we can read R2 bucket / credentials
set -a; source "$APP_DIR/.env.prod"; set +a

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup: $FILENAME"

# Dump from running postgres container
docker compose -f "$APP_DIR/docker-compose.prod.yml" exec -T postgres \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_DIR/$FILENAME"

echo "[$(date)] Upload to R2: $R2_BUCKET"
rclone copy "$BACKUP_DIR/$FILENAME" "r2:$R2_BUCKET/daily/" \
    --s3-access-key-id "$R2_ACCESS_KEY_ID" \
    --s3-secret-access-key "$R2_SECRET_ACCESS_KEY" \
    --s3-endpoint "$R2_ENDPOINT"

# Keep only last 7 local backups
ls -t "$BACKUP_DIR"/ojik_bms_*.sql.gz | tail -n +8 | xargs -r rm --

echo "[$(date)] Backup complete: $FILENAME"
