#!/usr/bin/env bash
# Install or update the Shishka host agent. Run as root from the repo root:
#   bash server_agent/install.sh <public-host-or-ip>
# Re-running updates agent.py and the unit but keeps the existing token.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE=/etc/shishka-agent.env
PROXY_HOST="${1:-}"

install -d -m 700 /opt/shishka-agent
install -m 600 "$SRC/agent.py" /opt/shishka-agent/agent.py
install -m 644 "$SRC/shishka-agent.service" /etc/systemd/system/shishka-agent.service

if [ ! -f "$ENV_FILE" ]; then
  TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  umask 077
  cat > "$ENV_FILE" <<EOF
AGENT_TOKEN=$TOKEN
AGENT_BIND=172.17.0.1
AGENT_PORT=8765
AWG_DIR=/root/awg
MTG_CONTAINER=mtproto-proxy
PROXY_HOST=$PROXY_HOST
PROXY_PORT=443
AWG_IFACE=awg0
CHECK_UNITS=docker,ssh,fail2ban
CHECK_CONTAINERS=shishka-bot,mtproto-proxy
CHECK_TCP=MTProto:127.0.0.1:443
EOF
  echo "Created $ENV_FILE"
elif [ -n "$PROXY_HOST" ]; then
  sed -i "s|^PROXY_HOST=.*|PROXY_HOST=$PROXY_HOST|" "$ENV_FILE"
fi

systemctl daemon-reload
systemctl enable --now shishka-agent
systemctl restart shishka-agent
sleep 1
systemctl --no-pager --lines=5 status shishka-agent || true

# Put the token into the bot's .env so docker compose passes it to the bot.
BOT_ENV="$(cd "$SRC/.." && pwd)/.env"
TOKEN="$(sed -n 's/^AGENT_TOKEN=//p' "$ENV_FILE")"
if [ -f "$BOT_ENV" ]; then
  sed -i '/^SERVER_AGENT_URL=/d;/^SERVER_AGENT_TOKEN=/d' "$BOT_ENV"
  printf 'SERVER_AGENT_URL=http://host.docker.internal:8765\nSERVER_AGENT_TOKEN=%s\n' "$TOKEN" >> "$BOT_ENV"
  echo "Updated $BOT_ENV; now run: docker compose up -d --build"
else
  echo "No $BOT_ENV found; add SERVER_AGENT_URL and SERVER_AGENT_TOKEN to the bot env manually"
fi
