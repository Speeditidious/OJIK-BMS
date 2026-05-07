#!/usr/bin/env bash
# Daily PostgreSQL backup → Cloudflare R2
# Prerequisites: rclone configured with an R2 remote named "r2"
# Cron example (daily 3 AM): 0 3 * * * /opt/ojik-bms/scripts/backup.sh >> /var/log/ojik-backup.log 2>&1
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ojik-bms}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/ojik-backups}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-$APP_DIR/docker-compose.prod.yml}"
R2_REMOTE="${R2_REMOTE:-r2}"
LOCAL_RETENTION="${LOCAL_RETENTION:-7}"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="ojik_bms_${DATE}.sql.gz"
TMP_FILE="$BACKUP_DIR/.${FILENAME}.tmp"

log() {
    echo "[$(date)] $*"
}

die() {
    log "ERROR: $*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

require_env() {
    local name="$1"
    [[ -n "${!name:-}" ]] || die "Missing required env var: $name"
}

load_env_var() {
    local name="$1"
    local line
    line=$(grep -E "^[[:space:]]*${name}=" "$ENV_FILE" | tail -n 1 || true)
    [[ -n "$line" ]] || return 0
    local value="${line#*=}"
    value="${value%%#*}"
    value="${value%"${value##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
        value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
        value="${value:1:${#value}-2}"
    fi
    printf -v "$name" '%s' "$value"
    export "$name"
}

validate_identifier() {
    local name="$1"
    local value="$2"
    [[ "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "$name must be a simple PostgreSQL identifier: $value"
}

cleanup() {
    rm -f "$TMP_FILE"
}
trap cleanup EXIT

[[ -f "$ENV_FILE" ]] || die "Env file not found: $ENV_FILE"
load_env_var POSTGRES_USER
load_env_var POSTGRES_DB
load_env_var R2_ACCESS_KEY_ID
load_env_var R2_SECRET_ACCESS_KEY
load_env_var R2_BUCKET
load_env_var R2_ENDPOINT

require_command docker
require_command gzip
require_command rclone

require_env POSTGRES_USER
require_env POSTGRES_DB
require_env R2_ACCESS_KEY_ID
require_env R2_SECRET_ACCESS_KEY
require_env R2_BUCKET
require_env R2_ENDPOINT

validate_identifier POSTGRES_USER "$POSTGRES_USER"
validate_identifier POSTGRES_DB "$POSTGRES_DB"
[[ "$LOCAL_RETENTION" =~ ^[0-9]+$ ]] || die "LOCAL_RETENTION must be a non-negative integer"

mkdir -p "$BACKUP_DIR"

compose_cmd=(
    docker compose
    --env-file "$ENV_FILE"
    -f "$COMPOSE_FILE"
    --project-directory "$APP_DIR"
)

log "Starting backup: $FILENAME"

# Dump from running postgres container
"${compose_cmd[@]}" exec -T postgres \
    pg_dump -U "$POSTGRES_USER" --dbname "$POSTGRES_DB" --no-password \
    | gzip -c > "$TMP_FILE"

[[ -s "$TMP_FILE" ]] || die "Backup file is empty: $TMP_FILE"
mv "$TMP_FILE" "$BACKUP_DIR/$FILENAME"

log "Upload to R2: $R2_BUCKET/daily/$FILENAME"
rclone copyto "$BACKUP_DIR/$FILENAME" "$R2_REMOTE:$R2_BUCKET/daily/$FILENAME" \
    --s3-access-key-id "$R2_ACCESS_KEY_ID" \
    --s3-secret-access-key "$R2_SECRET_ACCESS_KEY" \
    --s3-endpoint "$R2_ENDPOINT" \
    --s3-no-check-bucket

# Keep only last 7 local backups
if (( LOCAL_RETENTION > 0 )); then
    mapfile -t local_backups < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'ojik_bms_*.sql.gz' | sort -r)
    for old_backup in "${local_backups[@]:$LOCAL_RETENTION}"; do
        rm -f "$old_backup"
    done
fi

log "Backup complete: $FILENAME"
