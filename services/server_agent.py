"""
Client for the host agent (server_agent/agent.py) plus text formatting for the
owner's server panel.

aiohttp is imported lazily so the formatting helpers stay importable (and
testable) without the network stack.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

from config import config

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
EXPIRES_RE = re.compile(r"^[1-9][0-9]{0,2}[hdw]$")

STATUS_ICONS = {
    "active": "🟢",
    "recent": "🟡",
    "inactive": "⚪",
    "no_handshake": "⚪",
    "key_error": "🔴",
    "no_data": "⚪",
}


class ServerAgentError(Exception):
    """Agent unreachable, misconfigured or returned an error; message is user-facing."""


def is_configured() -> bool:
    return bool(config.server_agent.url and config.server_agent.token.get_secret_value())


class ServerAgentClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or config.server_agent.url).rstrip("/")
        self.token = token if token is not None else config.server_agent.token.get_secret_value()
        self.timeout = timeout or config.server_agent.timeout

    async def _request(self, method: str, path: str, json_body: dict | None = None, raw: bool = False) -> Any:
        if not self.base_url or not self.token:
            raise ServerAgentError("Агент сервера не настроен: нужны SERVER_AGENT_URL и SERVER_AGENT_TOKEN")
        import aiohttp

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.request(method, self.base_url + path, json=json_body, headers=headers) as resp:
                    data = await resp.read()
                    if resp.status >= 400:
                        raise ServerAgentError(error_message(resp.status, data))
                    if raw:
                        return data
                    return await resp.json(content_type=None)
        except ServerAgentError:
            raise
        except (aiohttp.ClientError, TimeoutError) as e:
            raise ServerAgentError(f"Агент сервера недоступен: {type(e).__name__}") from e

    async def server_status(self) -> dict:
        return await self._request("GET", "/server/status")

    async def services(self) -> dict:
        return await self._request("GET", "/services")

    async def awg_clients(self) -> list[dict]:
        return (await self._request("GET", "/awg/clients")).get("clients") or []

    async def awg_stats(self) -> list[dict]:
        return (await self._request("GET", "/awg/stats")).get("clients") or []

    async def awg_add(self, name: str, expires: str | None = None) -> dict:
        return await self._request("POST", "/awg/clients", {"name": name, "expires": expires})

    async def awg_remove(self, name: str) -> dict:
        return await self._request("DELETE", f"/awg/clients/{name}")

    async def awg_file(self, name: str, kind: str) -> bytes:
        return await self._request("GET", f"/awg/clients/{name}/files/{kind}", raw=True)

    async def proxy_status(self) -> dict:
        return await self._request("GET", "/proxy/status")

    async def proxy_restart(self) -> dict:
        return await self._request("POST", "/proxy/restart")

    async def proxy_link(self) -> dict:
        return await self._request("GET", "/proxy/link")


def error_message(status: int, body: bytes) -> str:
    import json

    try:
        detail = json.loads(body).get("error")
    except (ValueError, AttributeError):
        detail = None
    if status == 401:
        return "Агент отклонил токен (SERVER_AGENT_TOKEN не совпадает)"
    return detail or f"Агент ответил ошибкой {status}"


# ---------------------------------------------------------------------------
# input parsing


def parse_add_args(text: str | None) -> tuple[str, str | None]:
    """`имя [срок]` -> (name, expires). Raises ValueError with a user-facing message."""
    parts = (text or "").split()
    if not parts or len(parts) > 2:
        raise ValueError("Формат: <code>!vpn_add имя [срок]</code>, например <code>!vpn_add guest 7d</code>")
    name = parts[0]
    if not NAME_RE.fullmatch(name):
        raise ValueError("Имя: латиница, цифры, _ и -, до 32 символов, начинается с буквы или цифры")
    expires = parts[1].lower() if len(parts) == 2 else None
    if expires and not EXPIRES_RE.fullmatch(expires):
        raise ValueError("Срок: число и h/d/w, например <code>12h</code>, <code>7d</code>, <code>4w</code>")
    return name, expires


def parse_name_arg(text: str | None) -> str:
    name = (text or "").strip()
    if not NAME_RE.fullmatch(name):
        raise ValueError("Формат: <code>!vpn_del имя</code>")
    return name


# ---------------------------------------------------------------------------
# formatting (HTML parse mode)


def human_bytes(value: float | int | None) -> str:
    value = float(value or 0)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "Б" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} ТБ"


def human_duration(seconds: int | float) -> str:
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days} д {hours} ч"
    if hours:
        return f"{hours} ч {minutes} мин"
    return f"{minutes} мин"


def client_name(client: dict) -> str:
    return str(client.get("name") or client.get("client") or "?")


def format_handshake(ts: Any, now: float | None = None) -> str:
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return "нет"
    if ts <= 0:
        return "нет"
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    return human_duration(max(0, now - ts)) + " назад"


def merge_stats(clients: list[dict], stats: list[dict]) -> list[dict]:
    """Add traffic/handshake fields from `stats` to the `list` entries (by name)."""
    by_name = {client_name(s): s for s in stats}
    merged = []
    for c in clients:
        extra = {k: v for k, v in by_name.get(client_name(c), {}).items() if k not in c}
        merged.append({**c, **extra})
    return merged


def find_client(clients: list[dict], name: str) -> dict | None:
    return next((c for c in clients if client_name(c) == name), None)


def format_server_status(data: dict) -> str:
    mem_total = data.get("mem_total") or 0
    mem_used = mem_total - (data.get("mem_available") or 0)
    disk_total = data.get("disk_total") or 0
    disk_used = disk_total - (data.get("disk_free") or 0)
    load = ", ".join(f"{x:.2f}" for x in data.get("load") or [])
    lines = [
        "🖥 <b>Сервер</b>",
        f"Аптайм: {human_duration(data.get('uptime_seconds', 0))}",
        f"Нагрузка: {load}",
        f"Память: {human_bytes(mem_used)} / {human_bytes(mem_total)}",
        f"Диск: {human_bytes(disk_used)} / {human_bytes(disk_total)}",
        "",
        "🐳 <b>Контейнеры</b>",
    ]
    for c in data.get("containers") or []:
        icon = "🟢" if str(c.get("status", "")).startswith("Up") else "🔴"
        lines.append(f"{icon} {html.escape(str(c.get('name')))}: {html.escape(str(c.get('status')))}")
    return "\n".join(lines)


def format_clients(clients: list[dict]) -> str:
    if not clients:
        return "🔐 <b>VPN-клиенты</b>\nКлиентов нет."
    lines = [f"🔐 <b>VPN-клиенты</b> ({len(clients)})"]
    for c in clients:
        icon = STATUS_ICONS.get(str(c.get("status_code")), "⚪")
        ip = c.get("ip") or c.get("client_ip") or ""
        lines.append(f"{icon} <code>{html.escape(client_name(c))}</code> {html.escape(str(ip))}")
    lines.append("\nВыпустить ключ: <code>!vpn_add имя [срок]</code>")
    return "\n".join(lines)


def format_client(client: dict) -> str:
    name = client_name(client)
    lines = [f"🔑 <b>{html.escape(name)}</b>"]
    labels = {
        "ip": "IP",
        "client_ip": "IP",
        "client_ipv6": "IPv6",
        "status": "Статус",
        "expires": "Истекает",
        "expires_at": "Истекает",
    }
    for key, label in labels.items():
        if client.get(key) not in (None, ""):
            lines.append(f"{label}: {html.escape(str(client[key]))}")
    if "last_handshake" in client:
        lines.append(f"Рукопожатие: {format_handshake(client['last_handshake'])}")
    if "rx" in client or "tx" in client:
        lines.append(f"Трафик: ↓ {human_bytes(client.get('rx'))} ↑ {human_bytes(client.get('tx'))}")
    return "\n".join(lines)


KIND_LABELS = {"vpn": "VPN", "docker": "Контейнеры", "port": "Порты", "systemd": "Системные службы"}


def format_services(data: dict | None, agent_error: str | None = None) -> str:
    """Overview of what works: green/red per service, grouped by kind.

    `data=None` + `agent_error`: the agent itself is unreachable; the bot is
    obviously alive (it is answering), everything else is unknown.
    """
    header = "📊 <b>Состояние сервисов</b>"
    if data is None:
        return (
            f"{header}\n🟢 Бот: отвечает\n🔴 Агент сервера: {html.escape(agent_error or 'недоступен')}\n\n"
            "Остальное проверить нельзя, пока агент не работает. На сервере: "
            "<code>systemctl status shishka-agent</code>"
        )
    services = data.get("services") or []
    failed = [s for s in services if not s.get("ok")]
    summary = "✅ Всё работает" if not failed else f"⚠️ Не работает: {len(failed)} из {len(services)}"
    lines = [header, summary]
    for kind in ("vpn", "docker", "port", "systemd"):
        group = [s for s in services if s.get("kind") == kind]
        if not group:
            continue
        lines.append(f"\n<b>{KIND_LABELS[kind]}</b>")
        for svc in group:
            icon = "🟢" if svc.get("ok") else "🔴"
            lines.append(f"{icon} {html.escape(str(svc.get('name')))}: {html.escape(str(svc.get('detail', '')))}")
    return "\n".join(lines)


def format_proxy_status(data: dict) -> str:
    icon = "🟢" if data.get("running") else "🔴"
    return (
        "📡 <b>MTProto-прокси</b>\n"
        f"{icon} {html.escape(str(data.get('container')))}: {html.escape(str(data.get('status')))}\n"
        f"Запущен: {html.escape(str(data.get('started_at') or '?'))[:19].replace('T', ' ')}\n"
        f"Перезапусков: {data.get('restarts', 0)}"
    )
