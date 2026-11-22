#!/usr/bin/env bash
# Collect everything needed to move the server into one archive.
# Run as root on the OLD server, from anywhere:
#   bash /root/shishka-bot/deploy/backup.sh [--no-models] [--stop-bot]
#
#   --no-models  skip nsfw_model/ and ruspam_model/ (~700 MB); the new server
#                then downloads them from Hugging Face on first start
#   --stop-bot   stop the bot before copying its database (consistent copy;
#                do this right before the move so the new bot continues from here)
#
# Result: /root/shishka-backup-<date>.tar.gz (mode 600, contains secrets: VPN keys,
# bot token, proxy secret). Copy it to the new server and run deploy/bootstrap.sh.
set -euo pipefail

BOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AWG_DIR=/root/awg
MTG_CONTAINER="${MTG_CONTAINER:-mtproto-proxy}"
WITH_MODELS=1
STOP_BOT=0
for arg in "$@"; do
  case "$arg" in
    --no-models) WITH_MODELS=0 ;;
    --stop-bot) STOP_BOT=1 ;;
    *) echo "Неизвестный параметр: $arg" >&2; exit 2 ;;
  esac
done

[ "$(id -u)" -eq 0 ] || { echo "Запускайте от root" >&2; exit 1; }

STAMP="$(date +%Y%m%d-%H%M)"
WORK="$(mktemp -d)"
OUT_DIR="$WORK/shishka-backup"
ARCHIVE="/root/shishka-backup-$STAMP.tar.gz"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT_DIR"/{awg,mtproto,bot,agent,extra}
umask 077

step() { printf '\n==> %s\n' "$*"; }
warn() { printf '!! %s\n' "$*" >&2; }

# --- meta -------------------------------------------------------------------
step "Метаданные"
{
  echo "BACKUP_DATE=$STAMP"
  echo "SOURCE_HOST=$(hostname -f 2>/dev/null || hostname)"
  echo "BOT_REPO=$(git -C "$BOT_DIR" remote get-url origin)"
  echo "BOT_BRANCH=$(git -C "$BOT_DIR" rev-parse --abbrev-ref HEAD)"
  echo "BOT_COMMIT=$(git -C "$BOT_DIR" rev-parse HEAD)"
} > "$OUT_DIR/meta.env"
cat "$OUT_DIR/meta.env"

# --- AmneziaWG ----------------------------------------------------------------
step "AmneziaWG"
if [ -f "$AWG_DIR/manage_amneziawg.sh" ]; then
  touch "$WORK/marker"
  sleep 1
  bash "$AWG_DIR/manage_amneziawg.sh" --yes --no-color backup
  latest="$(find "$AWG_DIR/backups" -maxdepth 1 -name 'awg_backup_*.tar.gz' -newer "$WORK/marker" 2>/dev/null \
            | sort | tail -n1)"
  if [ -z "$latest" ]; then
    warn "manage_amneziawg.sh backup не создал новый архив в $AWG_DIR/backups"; exit 1
  fi
  cp "$latest" "$OUT_DIR/awg/awg_backup.tar.gz"
  cp "$AWG_DIR/awgsetup_cfg.init" "$OUT_DIR/awg/" 2>/dev/null || warn "нет awgsetup_cfg.init"
  cp /etc/amnezia/amneziawg/awg0.conf "$OUT_DIR/awg/" 2>/dev/null || warn "нет /etc/amnezia/amneziawg/awg0.conf"
  # Same installer version as the manage script that made the backup
  for f in /root/install_amneziawg.sh /root/install_amneziawg_en.sh "$AWG_DIR/install_amneziawg.sh"; do
    if [ -f "$f" ]; then cp "$f" "$OUT_DIR/awg/install_amneziawg.sh"; break; fi
  done
  [ -f "$OUT_DIR/awg/install_amneziawg.sh" ] || warn "установщик AmneziaWG не найден, bootstrap скачает актуальный"
  # Full client files too (old vpn:// links and QR, for reference)
  tar -C "$AWG_DIR" --exclude=backups -czf "$OUT_DIR/awg/awg_dir.tar.gz" .
else
  warn "AmneziaWG не найден ($AWG_DIR/manage_amneziawg.sh), пропускаю"
fi

# --- MTProto proxy ------------------------------------------------------------
step "MTProto-прокси ($MTG_CONTAINER)"
if docker inspect "$MTG_CONTAINER" >/dev/null 2>&1; then
  docker inspect "$MTG_CONTAINER" > "$WORK/mtg.json"
  python3 - "$WORK/mtg.json" > "$OUT_DIR/mtproto/mtproto.env" <<'PY'
import json, re, shlex, sys
c = json.load(open(sys.argv[1]))[0]
args = c.get("Args") or []
secret = next((a for a in reversed(args) if not a.startswith("-") and ":" not in a
               and re.fullmatch(r"[0-9A-Za-z_\-+/=]{16,}", a)), "")
bind = next((a for a in args if re.fullmatch(r"[0-9.]+:\d+", a)), "0.0.0.0:3128")
inner = bind.rsplit(":", 1)[1] + "/tcp"
ports = (c["HostConfig"].get("PortBindings") or {}).get(inner) or [{}]
policy = (c["HostConfig"].get("RestartPolicy") or {}).get("Name") or "unless-stopped"
values = {
    "MTG_CONTAINER": c["Name"].lstrip("/"),
    "MTG_IMAGE": c["Config"]["Image"],
    "MTG_SECRET": secret,
    "MTG_BIND": bind,
    "MTG_HOST_PORT": ports[0].get("HostPort") or "443",
    "MTG_RESTART": policy if policy != "no" else "unless-stopped",
}
if not secret:
    sys.exit("secret not found in container args")
for k, v in values.items():
    print(f"{k}={shlex.quote(v)}")
PY
  sed 's/^MTG_SECRET=.*/MTG_SECRET=<скрыт>/' "$OUT_DIR/mtproto/mtproto.env"
else
  warn "контейнер $MTG_CONTAINER не найден, пропускаю"
fi
for f in /root/start-mtproxy.sh /root/mtproto_config.txt; do
  if [ -f "$f" ]; then cp "$f" "$OUT_DIR/extra/"; fi
done

# --- bot ----------------------------------------------------------------------
step "Бот ($BOT_DIR)"
if [ "$STOP_BOT" -eq 1 ]; then
  (cd "$BOT_DIR" && docker compose stop)
  echo "Бот остановлен. На этом сервере его больше не запускайте (один токен = один бот)."
fi
cp "$BOT_DIR/.env" "$OUT_DIR/bot/.env"
cp "$BOT_DIR/config.toml" "$OUT_DIR/bot/config.toml"
if [ -d "$BOT_DIR/data" ]; then cp -a "$BOT_DIR/data" "$OUT_DIR/bot/data"; fi
if [ "$WITH_MODELS" -eq 1 ]; then
  for m in nsfw_model ruspam_model; do
    if [ -d "$BOT_DIR/$m" ]; then cp -a "$BOT_DIR/$m" "$OUT_DIR/bot/$m"; fi
  done
fi
du -sh "$OUT_DIR/bot"/* 2>/dev/null || true

# --- host agent ---------------------------------------------------------------
step "Агент сервера"
if [ -f /etc/shishka-agent.env ]; then cp /etc/shishka-agent.env "$OUT_DIR/agent/"; else warn "нет /etc/shishka-agent.env"; fi

# --- pack ---------------------------------------------------------------------
step "Упаковка"
tar -C "$WORK" -czf "$ARCHIVE" shishka-backup
chmod 600 "$ARCHIVE"
ls -lh "$ARCHIVE"
sha256sum "$ARCHIVE"

cat <<EOF

Готово: $ARCHIVE
В архиве секреты (ключи VPN, токен бота, секрет прокси), не выкладывайте его никуда.

Перенос на новый сервер (Ubuntu 22.04/24.04, root):
  scp $ARCHIVE root@NEW_IP:/root/
  ssh root@NEW_IP
  curl -fsSL https://raw.githubusercontent.com/Luno-o/shishka_bot/master/deploy/bootstrap.sh -o bootstrap.sh
  bash bootstrap.sh /root/$(basename "$ARCHIVE")
EOF
