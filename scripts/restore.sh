#!/usr/bin/env bash
# Restore PostgreSQL from a backup file (local or R2)
# Usage:
#   ./restore.sh /path/to/ojik_bms_20260327_030000.sql.gz   # from local file
#   ./restore.sh r2:ojik-bms-backups/daily/ojik_bms_20260327_030000.sql.gz  # from R2
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ojik-bms}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-$APP_DIR/docker-compose.prod.yml}"
R2_REMOTE="${R2_REMOTE:-r2}"
RESTORE_TMP_DIR="${RESTORE_TMP_DIR:-/tmp/ojik-restore}"

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

validate_identifier() {
    local name="$1"
    local value="$2"
    [[ "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "$name must be a simple PostgreSQL identifier: $value"
}

cleanup() {
    if [[ -n "${DOWNLOADED_FILE:-}" ]]; then
        rm -f "$DOWNLOADED_FILE"
    fi
}
trap cleanup EXIT

[[ -f "$ENV_FILE" ]] || die "Env file not found: $ENV_FILE"
set -a; source "$ENV_FILE"; set +a

require_command docker
require_command gunzip
require_command gzip

require_env POSTGRES_USER
require_env POSTGRES_DB

validate_identifier POSTGRES_USER "$POSTGRES_USER"
validate_identifier POSTGRES_DB "$POSTGRES_DB"

BACKUP_SRC="${1:?Usage: $0 <backup_file_or_r2_path>}"
LOCAL_FILE="$BACKUP_SRC"

if [[ "$BACKUP_SRC" == r2:* ]]; then
    require_command rclone
    require_env R2_ACCESS_KEY_ID
    require_env R2_SECRET_ACCESS_KEY
    require_env R2_ENDPOINT

    mkdir -p "$RESTORE_TMP_DIR"
    DOWNLOADED_FILE="$RESTORE_TMP_DIR/$(basename "$BACKUP_SRC")"
    log "Downloading from R2: $BACKUP_SRC"
    rclone copyto "$BACKUP_SRC" "$DOWNLOADED_FILE" \
        --s3-access-key-id "$R2_ACCESS_KEY_ID" \
        --s3-secret-access-key "$R2_SECRET_ACCESS_KEY" \
        --s3-endpoint "$R2_ENDPOINT"
    LOCAL_FILE="$DOWNLOADED_FILE"
fi

[[ -f "$LOCAL_FILE" ]] || die "Backup file not found: $LOCAL_FILE"
gzip -t "$LOCAL_FILE"

compose_cmd=(
    docker compose
    --env-file "$ENV_FILE"
    -f "$COMPOSE_FILE"
    --project-directory "$APP_DIR"
)

STAMP=$(date +%Y%m%d_%H%M%S)
RESTORE_DB="${POSTGRES_DB}_restore_${STAMP}"
OLD_DB="${POSTGRES_DB}_before_restore_${STAMP}"

log "Preparing restore into temporary database: $RESTORE_DB"
"${compose_cmd[@]}" exec -T postgres \
    createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" "$RESTORE_DB"

restore_failed=0
gunzip -c "$LOCAL_FILE" | "${compose_cmd[@]}" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$RESTORE_DB" || restore_failed=1

if (( restore_failed != 0 )); then
    log "Restore failed before touching the current database. Dropping temporary database: $RESTORE_DB"
    "${compose_cmd[@]}" exec -T postgres \
        dropdb --if-exists --force -U "$POSTGRES_USER" "$RESTORE_DB"
    exit 1
fi

echo "WARNING: This will replace the live database '$POSTGRES_DB'."
echo "The current database will be renamed to '$OLD_DB' and kept for manual rollback."
read -r -p "Type '$POSTGRES_DB' to continue: " CONFIRM
[[ "$CONFIRM" == "$POSTGRES_DB" ]] || {
    log "Aborted. Dropping temporary database: $RESTORE_DB"
    "${compose_cmd[@]}" exec -T postgres \
        dropdb --if-exists --force -U "$POSTGRES_USER" "$RESTORE_DB"
    exit 1
}

log "Stopping API, celery services..."
"${compose_cmd[@]}" stop api celery celery-beat

log "Swapping restored database into place..."
if ! "${compose_cmd[@]}" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$POSTGRES_DB', '$RESTORE_DB') AND pid <> pg_backend_pid();"; then
    log "Failed to terminate database sessions. Restarting services without changing the live database."
    "${compose_cmd[@]}" up -d
    exit 1
fi

if ! "${compose_cmd[@]}" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
    -c "ALTER DATABASE \"$POSTGRES_DB\" RENAME TO \"$OLD_DB\";"; then
    log "Failed to rename live database. Restarting services without changing the live database."
    "${compose_cmd[@]}" up -d
    exit 1
fi

if ! "${compose_cmd[@]}" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
    -c "ALTER DATABASE \"$RESTORE_DB\" RENAME TO \"$POSTGRES_DB\";"; then
    log "Failed to promote restored database. Attempting rollback rename from $OLD_DB to $POSTGRES_DB."
    "${compose_cmd[@]}" exec -T postgres \
        psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
        -c "ALTER DATABASE \"$OLD_DB\" RENAME TO \"$POSTGRES_DB\";" || true
    "${compose_cmd[@]}" up -d
    exit 1
fi

log "Restarting services..."
"${compose_cmd[@]}" up -d

log "Restore complete. Previous database retained as: $OLD_DB"
log "After verification, remove it manually with: docker compose --env-file \"$ENV_FILE\" -f \"$COMPOSE_FILE\" --project-directory \"$APP_DIR\" exec -T postgres dropdb --if-exists --force -U \"$POSTGRES_USER\" \"$OLD_DB\""
