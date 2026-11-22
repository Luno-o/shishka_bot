#!/usr/bin/env bash
# Bring up the whole stack on a NEW server from a deploy/backup.sh archive:
# Docker, AmneziaWG (clients and keys restored), MTProto proxy (same secret),
# the bot (same .env, database, models) and the host agent.
#
# Fresh Ubuntu 22.04/24.04, as root:
#   bash bootstrap.sh /root/shishka-backup-YYYYMMDD-HHMM.tar.gz [--host=IP_or_domain]
#
# AmneziaWG needs 2 reboots (kernel module via DKMS). The script reboots the
# server itself and continues after boot (systemd unit shishka-bootstrap).
# Progress: tail -f /var/log/shishka-bootstrap.log
# Re-running is safe: finished steps are skipped.
set -euo pipefail

STATE_DIR=/var/lib/shishka-bootstrap
LOG=/var/log/shishka-bootstrap.log
RESTORE=/root/shishka-restore
BOT_DIR=/root/shishka-bot
AWG_DIR=/root/awg
UNIT=/etc/systemd/system/shishka-bootstrap.service
MAX_REBOOTS=4

ARCHIVE=""
HOST=""
for arg in "$@"; do
  case "$arg" in
    --host=*) HOST="${arg#--host=}" ;;
    -*) echo "Неизвестный параметр: $arg" >&2; exit 2 ;;
    *) ARCHIVE="$(readlink -f "$arg")" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || { echo "Запускайте от root" >&2; exit 1; }
mkdir -p "$STATE_DIR"
[ -n "$ARCHIVE" ] || ARCHIVE="$(cat "$STATE_DIR/archive" 2>/dev/null || true)"
[ -n "$HOST" ] || HOST="$(cat "$STATE_DIR/host" 2>/dev/null || true)"
[ -f "$ARCHIVE" ] || { echo "Укажите архив: bash bootstrap.sh /root/shishka-backup-....tar.gz" >&2; exit 2; }
echo "$ARCHIVE" > "$STATE_DIR/archive"

exec > >(tee -a "$LOG") 2>&1

step() { printf '\n==> [%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
done_step() { [ -f "$STATE_DIR/$1.done" ]; }
mark() { touch "$STATE_DIR/$1.done"; }
die() { printf '!! %s\n' "$*"; exit 1; }

# ---------------------------------------------------------------------------
step "Базовые пакеты и Docker"
if ! done_step base; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  apt-get install -y -q git curl ca-certificates python3 ufw tar
  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
  fi
  systemctl enable --now docker
  docker compose version >/dev/null || die "нет docker compose plugin"
  mark base
fi

# ---------------------------------------------------------------------------
step "Распаковка архива"
if ! done_step unpack; then
  rm -rf "$RESTORE"
  mkdir -p "$RESTORE"
  tar -C "$RESTORE" -xzf "$ARCHIVE"
  chmod -R go-rwx "$RESTORE"
  mark unpack
fi
SRC="$RESTORE/shishka-backup"
# shellcheck disable=SC1091
. "$SRC/meta.env"

if [ -z "$HOST" ]; then
  HOST="$(curl -4 -fs --max-time 5 https://ifconfig.me || curl -4 -fs --max-time 5 https://api.ipify.org || true)"
  [ -n "$HOST" ] || die "не удалось определить внешний IP, передайте --host=IP"
fi
echo "$HOST" > "$STATE_DIR/host"
echo "Внешний адрес: $HOST"

# ---------------------------------------------------------------------------
step "Автопродолжение после перезагрузок"
if [ ! -f "$UNIT" ]; then
  cat > "$UNIT" <<EOF
[Unit]
Description=Shishka bootstrap (resumes after reboot)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash $BOT_DIR/deploy/bootstrap.sh
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable shishka-bootstrap.service
fi

# ---------------------------------------------------------------------------
step "Код бота ($BOT_REPO, $BOT_BRANCH)"
if ! done_step repo; then
  if [ ! -d "$BOT_DIR/.git" ]; then
    git clone --branch "$BOT_BRANCH" "$BOT_REPO" "$BOT_DIR"
  fi
  cp "$SRC/bot/.env" "$BOT_DIR/.env"
  cp "$SRC/bot/config.toml" "$BOT_DIR/config.toml"
  chmod 600 "$BOT_DIR/.env"
  if [ -d "$SRC/bot/data" ]; then
    mkdir -p "$BOT_DIR/data"
    cp -a "$SRC/bot/data/." "$BOT_DIR/data/"
  fi
  for m in nsfw_model ruspam_model; do
    if [ -d "$SRC/bot/$m" ]; then
      rm -rf "${BOT_DIR:?}/$m"
      cp -a "$SRC/bot/$m" "$BOT_DIR/$m"
    fi
  done
  # The container runs as uid 1000 and writes the database
  chown -R 1000:1000 "$BOT_DIR/data"
  mark repo
fi

# ---------------------------------------------------------------------------
step "AmneziaWG"
if ! done_step awg; then
  if ! awg show awg0 >/dev/null 2>&1; then
    INSTALLER=/root/install_amneziawg.sh
    if [ ! -f "$INSTALLER" ]; then
      if [ -f "$SRC/awg/install_amneziawg.sh" ]; then
        cp "$SRC/awg/install_amneziawg.sh" "$INSTALLER"
      else
        curl -fsSL https://raw.githubusercontent.com/bivlked/amneziawg-installer/main/install_amneziawg.sh -o "$INSTALLER"
      fi
    fi
    # Same port / subnet / routing as on the old server
    AWG_PORT=443; AWG_TUNNEL_SUBNET=10.9.9.1/24; ALLOWED_IPS_MODE=2; ALLOWED_IPS=""
    if [ -f "$SRC/awg/awgsetup_cfg.init" ]; then
      set +u
      # shellcheck disable=SC1091
      . "$SRC/awg/awgsetup_cfg.init"
      set -u
    fi
    case "${ALLOWED_IPS_MODE:-2}" in
      1) ROUTE=(--route-all) ;;
      3) ROUTE=("--route-custom=$ALLOWED_IPS") ;;
      *) ROUTE=(--route-amnezia) ;;
    esac
    reboots="$(cat "$STATE_DIR/reboots" 2>/dev/null || echo 0)"
    echo "Установка AmneziaWG: порт $AWG_PORT, подсеть $AWG_TUNNEL_SUBNET, маршруты ${ROUTE[*]}, перезагрузок было $reboots"
    set +e
    bash "$INSTALLER" --yes "--port=$AWG_PORT" "--subnet=$AWG_TUNNEL_SUBNET" "--endpoint=$HOST" "${ROUTE[@]}"
    rc=$?
    set -e
    echo "Установщик завершился с кодом $rc"
    if ! awg show awg0 >/dev/null 2>&1; then
      [ "$reboots" -lt "$MAX_REBOOTS" ] || die "AmneziaWG не поднялся после $reboots перезагрузок, смотрите $LOG"
      echo $((reboots + 1)) > "$STATE_DIR/reboots"
      echo "Нужна перезагрузка. После старта сервер продолжит сам (журнал: $LOG)."
      sync
      systemctl reboot
      exit 0
    fi
  fi

  if ! done_step awg_restore; then
    if [ -f "$SRC/awg/awg_backup.tar.gz" ]; then
      mkdir -p "$AWG_DIR/backups"
      cp "$SRC/awg/awg_backup.tar.gz" "$AWG_DIR/backups/awg_backup_migrated.tar.gz"
      bash "$AWG_DIR/manage_amneziawg.sh" --yes --no-color restore "$AWG_DIR/backups/awg_backup_migrated.tar.gz"
      # New server IP into every client config; keys stay the same
      bash "$AWG_DIR/manage_amneziawg.sh" --yes --no-color regen
      bash "$AWG_DIR/manage_amneziawg.sh" --yes --no-color restart || true
    fi
    mark awg_restore
  fi
  awg show awg0 >/dev/null 2>&1 || die "awg0 не поднят после восстановления"
  mark awg
fi

# ---------------------------------------------------------------------------
step "MTProto-прокси"
if ! done_step mtg; then
  if [ -f "$SRC/mtproto/mtproto.env" ]; then
    # shellcheck disable=SC1091
    . "$SRC/mtproto/mtproto.env"
    docker rm -f "$MTG_CONTAINER" >/dev/null 2>&1 || true
    docker run -d --name "$MTG_CONTAINER" --restart "$MTG_RESTART" \
      -p "$MTG_HOST_PORT:${MTG_BIND##*:}" \
      "$MTG_IMAGE" simple-run "$MTG_BIND" "$MTG_SECRET"
    ufw allow "$MTG_HOST_PORT/tcp" comment "MTProto proxy" || true
  else
    echo "В архиве нет прокси, пропускаю"
  fi
  mark mtg
fi

# ---------------------------------------------------------------------------
step "Бот"
if ! done_step bot; then
  (cd "$BOT_DIR" && docker compose up -d --build)
  mark bot
fi

# ---------------------------------------------------------------------------
step "Агент сервера"
if ! done_step agent; then
  if [ -f "$SRC/agent/shishka-agent.env" ] && [ ! -f /etc/shishka-agent.env ]; then
    install -m 600 "$SRC/agent/shishka-agent.env" /etc/shishka-agent.env
  fi
  bash "$BOT_DIR/server_agent/install.sh" "$HOST"
  ufw allow from 172.16.0.0/12 to 172.17.0.1 port 8765 proto tcp comment shishka-agent || true
  # install.sh rewrote SERVER_AGENT_* in .env: recreate the bot so it sees them
  (cd "$BOT_DIR" && docker compose up -d --force-recreate)
  mark agent
fi

# ---------------------------------------------------------------------------
step "Проверка"
systemctl disable shishka-bootstrap.service >/dev/null 2>&1 || true
rm -f "$UNIT"
systemctl daemon-reload
sleep 5
TOKEN="$(sed -n 's/^AGENT_TOKEN=//p' /etc/shishka-agent.env)"
curl -fs -H "Authorization: Bearer $TOKEN" http://172.17.0.1:8765/services | python3 -c '
import json, sys
data = json.load(sys.stdin)
for s in data["services"]:
    print(("OK  " if s["ok"] else "FAIL"), s["name"], "-", s.get("detail", ""))
print("\nВсё работает" if data["ok"] else "\nЕсть проблемы, смотрите выше")
' || echo "Агент не ответил: systemctl status shishka-agent"
LINK="$(curl -fs -H "Authorization: Bearer $TOKEN" http://172.17.0.1:8765/proxy/link \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["https"])' 2>/dev/null || true)"

cat <<EOF

Готово. Что осталось сделать вручную:
  1. Старый сервер: остановите бота (docker compose stop), иначе два бота с одним токеном мешают друг другу.
  2. VPN: ключи клиентов прежние, но адрес сервера новый. Разошлите новые конфиги:
     в боте !server → VPN-ключи → клиент → «Для Amnezia».
  3. Прокси: секрет прежний, новая ссылка: ${LINK:-смотрите !server → Прокси → Ссылка}
  4. Если в DNS есть записи на старый IP (например, домен сервера), обновите их на $HOST.
Журнал: $LOG
Распакованный архив с секретами: $RESTORE (удалите, когда убедитесь, что всё работает).
EOF
mark finished
