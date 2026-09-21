#!/usr/bin/env bash
#
# backup_db.sh — one-command remote backup of the Шишка-бот database.
#
# Run this ON YOUR LAPTOP (not on the server). It connects to the server over
# SSH, makes a safe, consistent snapshot of the bot's database (it does NOT
# need to be stopped first — SQLite's own ".backup" command and pg_dump /
# mysqldump are all safe to run against a live database), downloads the
# snapshot, and cleans up after itself.
#
# Usage:
#   ./scripts/backup_db.sh -H server.example.com -u deploy [options]
#
# Required:
#   -H, --host        Server hostname or IP
#
# Common options:
#   -u, --user        SSH user (default: current local user)
#   -p, --port        SSH port (default: 22)
#   -i, --identity    Path to SSH private key
#   -d, --remote-dir  Path to the bot's directory on the server
#                      (default: ~/shishka_bot)
#   -o, --out-dir     Where to store backups locally (default: ./backups)
#   -k, --keep        How many local backups to keep, oldest deleted first
#                      (default: 14, use 0 to keep everything)
#   -q, --quiet       Only print the final result
#   -h, --help        Show this help
#
# Examples:
#   ./scripts/backup_db.sh -H 203.0.113.10 -u root
#   ./scripts/backup_db.sh -H bot.mydomain.com -u deploy -i ~/.ssh/id_ed25519 \
#       -d /opt/shishka_bot -o ~/shishka-backups -k 30
#
# The script figures out the database type (SQLite / PostgreSQL / MySQL) by
# reading DB_URL from the bot's .env (falling back to config.toml) on the
# server, so in the common case you only need --host and --user.
#
# Restoring:
#   SQLite         -> stop the bot, replace db.sqlite (or whatever DB_URL
#                     points to) with the downloaded *.sqlite3 file, start
#                     the bot again.
#   Postgres/MySQL -> gunzip the .sql.gz file and pipe it into
#                     psql / mysql against an (empty) target database.
#
# Scheduling automatic backups:
#   Add a line like this to your laptop's crontab (crontab -e) to back up
#   every night at 03:00:
#     0 3 * * * /path/to/shishka_bot/scripts/backup_db.sh -H your.server -u deploy -q

set -euo pipefail

# --- defaults ----------------------------------------------------------------
SSH_HOST=""
SSH_USER="${USER:-root}"
SSH_PORT="22"
SSH_KEY=""
REMOTE_DIR="~/shishka_bot"
OUT_DIR="./backups"
KEEP="14"
QUIET="0"

# --- helpers -------------------------------------------------------------------
log() { [ "$QUIET" = "1" ] || echo "[backup_db] $*"; }
die() { echo "[backup_db] ОШИБКА: $*" >&2; exit 1; }

print_help() {
    sed -n '2,45p' "$0" | sed 's/^# \{0,1\}//'
}

# --- argument parsing ----------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        -H|--host) SSH_HOST="$2"; shift 2 ;;
        -u|--user) SSH_USER="$2"; shift 2 ;;
        -p|--port) SSH_PORT="$2"; shift 2 ;;
        -i|--identity) SSH_KEY="$2"; shift 2 ;;
        -d|--remote-dir) REMOTE_DIR="$2"; shift 2 ;;
        -o|--out-dir) OUT_DIR="$2"; shift 2 ;;
        -k|--keep) KEEP="$2"; shift 2 ;;
        -q|--quiet) QUIET="1"; shift ;;
        -h|--help) print_help; exit 0 ;;
        *) die "Неизвестный параметр: $1 (см. --help)" ;;
    esac
done

[ -n "$SSH_HOST" ] || { print_help; die "не указан сервер (--host)"; }

command -v ssh  >/dev/null 2>&1 || die "нужна команда 'ssh' (установите OpenSSH)"
command -v scp  >/dev/null 2>&1 || die "нужна команда 'scp' (установите OpenSSH)"

SSH_OPTS=(-p "$SSH_PORT" -o BatchMode=no -o ConnectTimeout=15)
[ -n "$SSH_KEY" ] && SSH_OPTS+=(-i "$SSH_KEY")

SSH_TARGET="${SSH_USER}@${SSH_HOST}"

mkdir -p "$OUT_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REMOTE_TMP_BASE="/tmp/shishka_backup_${TIMESTAMP}"

log "Подключаюсь к ${SSH_TARGET}:${SSH_PORT} ..."

# Variables are passed to the remote shell as an env-var prefix so the
# heredoc below can stay fully single-quoted (no local expansion, no
# quoting headaches).
REMOTE_CMD="REMOTE_DIR=$(printf '%q' "$REMOTE_DIR") TIMESTAMP=$(printf '%q' "$TIMESTAMP") REMOTE_TMP_BASE=$(printf '%q' "$REMOTE_TMP_BASE") bash -s"

RAW_OUTPUT="$(ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$REMOTE_CMD" <<'REMOTE_SCRIPT'
set -eu
cd "$REMOTE_DIR" 2>/dev/null || { echo "FAIL Каталог бота не найден: $REMOTE_DIR"; exit 1; }

DB_URL=""
if [ -f .env ]; then
    DB_URL="$(grep -E '^DB_URL=' .env | tail -n1 | cut -d= -f2-)"
    # strip optional surrounding quotes ("..." or '...')
    DB_URL="${DB_URL%\"}"; DB_URL="${DB_URL#\"}"
    DB_URL="${DB_URL%\'}"; DB_URL="${DB_URL#\'}"
fi
if [ -z "$DB_URL" ] && [ -f config.toml ]; then
    DB_URL="$(grep -E '^[[:space:]]*url[[:space:]]*=' config.toml | tail -n1 | sed -E 's/^[^=]*=[[:space:]]*//')"
    DB_URL="${DB_URL%\"}"; DB_URL="${DB_URL#\"}"
    DB_URL="${DB_URL%\'}"; DB_URL="${DB_URL#\'}"
fi
if [ -z "$DB_URL" ]; then
    DB_URL="sqlite+aiosqlite:///db.sqlite"
    echo "ПРЕДУПРЕЖДЕНИЕ: DB_URL не найден в .env/config.toml, использую значение по умолчанию: $DB_URL" >&2
fi

case "$DB_URL" in
    sqlite*)
        DB_PATH="$(echo "$DB_URL" | sed -E 's#^sqlite\+?[a-z]*:///##')"
        case "$DB_PATH" in
            /*) : ;;
            *) DB_PATH="$REMOTE_DIR/$DB_PATH" ;;
        esac
        [ -f "$DB_PATH" ] || { echo "FAIL Файл базы данных не найден: $DB_PATH"; exit 1; }

        OUT_FILE="${REMOTE_TMP_BASE}.sqlite3"
        if command -v sqlite3 >/dev/null 2>&1; then
            # ".backup" is SQLite's own safe-copy command: it works correctly
            # even while the bot is running and writing to the database.
            sqlite3 "$DB_PATH" ".backup '${OUT_FILE}'"
        else
            echo "ПРЕДУПРЕЖДЕНИЕ: sqlite3 CLI не найден на сервере, копирую файл напрямую (безопаснее сначала остановить бота)" >&2
            cp "$DB_PATH" "$OUT_FILE"
        fi
        gzip -f "$OUT_FILE"
        echo "OK sqlite ${OUT_FILE}.gz"
        ;;
    postgres://*|postgresql://*)
        command -v pg_dump >/dev/null 2>&1 || { echo "FAIL pg_dump не установлен на сервере"; exit 1; }
        OUT_FILE="${REMOTE_TMP_BASE}.sql.gz"
        PG_URL="$(echo "$DB_URL" | sed -E 's#^postgresql\+[a-z0-9]+://#postgresql://#')"
        pg_dump --no-owner --no-privileges "$PG_URL" | gzip > "$OUT_FILE"
        echo "OK postgres ${OUT_FILE}"
        ;;
    mysql://*)
        command -v mysqldump >/dev/null 2>&1 || { echo "FAIL mysqldump не установлен на сервере"; exit 1; }
        # mysql://user:pass@host:port/dbname
        CONN="$(echo "$DB_URL" | sed -E 's#^mysql\+?[a-z0-9]*://##')"
        USERPASS="${CONN%%@*}"; HOSTPORTDB="${CONN#*@}"
        DB_USER="${USERPASS%%:*}"; DB_PASS="${USERPASS#*:}"
        HOSTPORT="${HOSTPORTDB%%/*}"; DB_NAME="${HOSTPORTDB#*/}"
        DB_HOST="${HOSTPORT%%:*}"; DB_PORT="${HOSTPORT#*:}"
        [ "$DB_PORT" = "$DB_HOST" ] && DB_PORT="3306"
        OUT_FILE="${REMOTE_TMP_BASE}.sql.gz"
        MYSQL_PWD="$DB_PASS" mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME" | gzip > "$OUT_FILE"
        echo "OK mysql ${OUT_FILE}"
        ;;
    *)
        echo "FAIL Неизвестный тип DB_URL: $DB_URL"
        exit 1
        ;;
esac
REMOTE_SCRIPT
)" || die "не удалось выполнить резервное копирование на сервере"

RESULT="$(echo "$RAW_OUTPUT" | tail -n1)"
[ -n "$QUIET" ] && [ "$QUIET" != "1" ] || true
if [ "$QUIET" != "1" ]; then
    echo "$RAW_OUTPUT" | sed '$d' | sed 's/^/[server] /' >&2 || true
fi

STATUS="$(echo "$RESULT" | awk '{print $1}')"
BACKEND="$(echo "$RESULT" | awk '{print $2}')"
REMOTE_FILE="$(echo "$RESULT" | awk '{print $3}')"

[ "$STATUS" = "OK" ] || die "сервер вернул ошибку: $RESULT"

log "Бэкап на сервере готов (${BACKEND}): ${REMOTE_FILE}"
log "Скачиваю на ноутбук в ${OUT_DIR} ..."

LOCAL_FILE="${OUT_DIR}/$(basename "$REMOTE_FILE")"
scp "${SSH_OPTS[@]}" "${SSH_TARGET}:${REMOTE_FILE}" "$LOCAL_FILE" \
    || die "не удалось скачать файл бэкапа"

# Clean up the temp file on the server no matter what.
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "rm -f '${REMOTE_FILE}'" || true

SIZE="$(du -h "$LOCAL_FILE" | cut -f1)"
log "Скачано: ${LOCAL_FILE} (${SIZE})"

# --- retention: keep only the last N backups locally ---------------------------
if [ "$KEEP" != "0" ]; then
    # shellcheck disable=SC2012
    ls -1t "${OUT_DIR}"/shishka_backup_*.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
        log "Удаляю старый бэкап: $old"
        rm -f -- "$old"
    done
fi

log "Резервная копия успешно сохранена: ${LOCAL_FILE}"
