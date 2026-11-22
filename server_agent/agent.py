#!/usr/bin/env python3
"""
Shishka host agent: a tiny HTTP API on the VPS host for the bot's owner panel.

Runs as root under systemd (see server_agent/README.md). Standard library only,
so it needs nothing beyond the system python3.

Every action is whitelisted: the bot can list/add/remove AmneziaWG clients,
fetch their config files, check/restart the MTProto proxy container and read
basic server status. Nothing else, no shell, no arbitrary arguments.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import quote, unquote, urlsplit

log = logging.getLogger("shishka-agent")

# first char alphanumeric: a leading "-" would be parsed by the script as an option
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
EXPIRES_RE = re.compile(r"^[1-9][0-9]{0,2}[hdw]$")
SECRET_RE = re.compile(r"^(ee|dd)?[0-9A-Za-z_\-+/=]{16,}$")
MAX_BODY = 4096

# kind -> (file suffix, content type)
CLIENT_FILES = {
    "conf": (".conf", "text/plain; charset=utf-8"),
    "qr": (".png", "image/png"),
    "vpnuri": (".vpnuri", "text/plain; charset=utf-8"),
    "vpnuri_qr": (".vpnuri.png", "image/png"),
}

Runner = Callable[[list[str], float], "tuple[int, str, str]"]


def run_command(args: list[str], timeout: float) -> tuple[int, str, str]:
    """Run a command without a shell; never raises on non-zero exit."""
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, "", str(e)
    return proc.returncode, proc.stdout, proc.stderr


@dataclass
class AgentConfig:
    token: str
    bind: str = "172.17.0.1"
    port: int = 8765
    awg_dir: Path = Path("/root/awg")
    awg_manage: Path = Path("/root/awg/manage_amneziawg.sh")
    mtg_container: str = "mtproto-proxy"
    proxy_host: str = ""
    proxy_port: int = 443
    awg_iface: str = "awg0"
    units: tuple[str, ...] = ("docker", "ssh", "fail2ban")
    containers: tuple[str, ...] = ("shishka-bot", "mtproto-proxy")
    # (label, host, port) TCP ports that must accept connections
    tcp_checks: tuple[tuple[str, str, int], ...] = (("MTProto :443", "127.0.0.1", 443),)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "AgentConfig":
        env = dict(os.environ if env is None else env)
        token = env.get("AGENT_TOKEN", "").strip()
        if len(token) < 24:
            raise ValueError("AGENT_TOKEN must be set (at least 24 characters)")
        awg_dir = Path(env.get("AWG_DIR", "/root/awg"))
        return cls(
            token=token,
            bind=env.get("AGENT_BIND", "172.17.0.1"),
            port=int(env.get("AGENT_PORT", "8765")),
            awg_dir=awg_dir,
            awg_manage=Path(env.get("AWG_MANAGE", str(awg_dir / "manage_amneziawg.sh"))),
            mtg_container=env.get("MTG_CONTAINER", "mtproto-proxy"),
            proxy_host=env.get("PROXY_HOST", "").strip(),
            proxy_port=int(env.get("PROXY_PORT", "443")),
            awg_iface=env.get("AWG_IFACE", "awg0"),
            units=_csv(env.get("CHECK_UNITS", "docker,ssh,fail2ban")),
            containers=_csv(env.get("CHECK_CONTAINERS", "shishka-bot,mtproto-proxy")),
            tcp_checks=tuple(_parse_tcp(x) for x in _csv(env.get("CHECK_TCP", "MTProto:127.0.0.1:443"))),
        )


def _csv(value: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in value.split(",") if x.strip())


def _parse_tcp(item: str) -> tuple[str, str, int]:
    """'label:host:port' -> (label :port, host, port)."""
    label, host, port = item.rsplit(":", 2)
    return f"{label} :{port}", host, int(port)


def tcp_open(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Response:
    status: int = 200
    body: bytes = b""
    content_type: str = "application/json"

    @classmethod
    def json(cls, data: object, status: int = 200) -> "Response":
        return cls(status, json.dumps(data, ensure_ascii=False).encode(), "application/json")


def _tail(text: str, lines: int = 15) -> str:
    """Last lines of script output without ANSI colors (for error messages)."""
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")
    return "\n".join(clean.strip().splitlines()[-lines:])


def validate_name(name: str) -> str:
    if not NAME_RE.fullmatch(name or ""):
        raise ApiError(400, "Имя клиента: 1-32 символа (латиница, цифры, _ и -), начинается с буквы или цифры")
    return name


def validate_expires(expires: str | None) -> str | None:
    if expires in (None, ""):
        return None
    if not EXPIRES_RE.fullmatch(str(expires)):
        raise ApiError(400, "Срок: число и h/d/w, например 12h, 7d, 4w")
    return str(expires)


def extract_mtg_secret(args: list[str]) -> str | None:
    """`mtg simple-run [flags] <bind> <secret>` -> secret (last plausible argument)."""
    for arg in reversed(args):
        if arg.startswith("-") or ":" in arg:
            continue
        if SECRET_RE.fullmatch(arg):
            return arg
    return None


def parse_meminfo(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[key.strip()] = int(parts[0]) * 1024
    return values


@dataclass
class Agent:
    config: AgentConfig
    runner: Runner = run_command
    proc_root: Path = Path("/proc")
    tcp_probe: Callable[[str, int], bool] = tcp_open
    _awg_lock: threading.Lock = field(default_factory=threading.Lock)

    # ---- helpers -------------------------------------------------------

    def _manage(self, *args: str, timeout: float = 120) -> tuple[int, str, str]:
        cmd = ["bash", str(self.config.awg_manage), "--no-color", *args]
        return self.runner(cmd, timeout)

    def _manage_json(self, command: str) -> object:
        rc, out, err = self._manage("--json", command, timeout=60)
        if rc != 0:
            raise ApiError(502, f"{command} завершился с кодом {rc}: {_tail(err or out)}")
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            raise ApiError(502, f"{command}: скрипт вернул не JSON: {_tail(out, 5)}")

    def _client_exists(self, name: str) -> bool:
        return (self.config.awg_dir / f"{name}.conf").is_file()

    def _docker(self, *args: str, timeout: float = 60) -> tuple[int, str, str]:
        return self.runner(["docker", *args], timeout)

    # ---- AmneziaWG -----------------------------------------------------

    def awg_list(self) -> Response:
        return Response.json({"clients": self._manage_json("list")})

    def awg_stats(self) -> Response:
        return Response.json({"clients": self._manage_json("stats")})

    def awg_add(self, body: dict) -> Response:
        name = validate_name(str(body.get("name", "")))
        expires = validate_expires(body.get("expires"))
        with self._awg_lock:
            if self._client_exists(name):
                raise ApiError(409, f"Клиент {name} уже существует")
            args = ["--yes"]
            if expires:
                args.append(f"--expires={expires}")
            rc, out, err = self._manage(*args, "add", name, timeout=180)
            if rc != 0 or not self._client_exists(name):
                raise ApiError(502, f"Не удалось добавить {name} (код {rc}): {_tail(err or out)}")
        return Response.json({"ok": True, "name": name, "expires": expires}, status=201)

    def awg_remove(self, name: str) -> Response:
        name = validate_name(name)
        with self._awg_lock:
            if not self._client_exists(name):
                raise ApiError(404, f"Клиент {name} не найден")
            rc, out, err = self._manage("--yes", "remove", name, timeout=180)
            if rc != 0 or self._client_exists(name):
                raise ApiError(502, f"Не удалось удалить {name} (код {rc}): {_tail(err or out)}")
        return Response.json({"ok": True, "name": name})

    def awg_file(self, name: str, kind: str) -> Response:
        name = validate_name(name)
        if kind not in CLIENT_FILES:
            raise ApiError(404, "Неизвестный тип файла")
        suffix, content_type = CLIENT_FILES[kind]
        path = self.config.awg_dir / f"{name}{suffix}"
        if not path.is_file():
            raise ApiError(404, f"Файл {path.name} не найден")
        return Response(200, path.read_bytes(), content_type)

    # ---- MTProto proxy -------------------------------------------------

    def proxy_status(self) -> Response:
        rc, out, err = self._docker("inspect", "--format", "{{json .State}}", self.config.mtg_container)
        if rc != 0:
            raise ApiError(502, f"docker inspect: {_tail(err or out, 3)}")
        state = json.loads(out)
        return Response.json({
            "container": self.config.mtg_container,
            "status": state.get("Status"),
            "running": bool(state.get("Running")),
            "started_at": state.get("StartedAt"),
            "restarts": state.get("RestartCount"),
        })

    def proxy_restart(self) -> Response:
        rc, out, err = self._docker("restart", self.config.mtg_container, timeout=90)
        if rc != 0:
            raise ApiError(502, f"docker restart: {_tail(err or out, 3)}")
        return self.proxy_status()

    def proxy_link(self) -> Response:
        if not self.config.proxy_host:
            raise ApiError(503, "PROXY_HOST не задан в настройках агента")
        rc, out, err = self._docker("inspect", "--format", "{{json .Args}}", self.config.mtg_container)
        if rc != 0:
            raise ApiError(502, f"docker inspect: {_tail(err or out, 3)}")
        secret = extract_mtg_secret(json.loads(out) or [])
        if not secret:
            raise ApiError(502, "Не удалось найти секрет в аргументах контейнера")
        query = f"server={quote(self.config.proxy_host)}&port={self.config.proxy_port}&secret={quote(secret)}"
        return Response.json({
            "tg": f"tg://proxy?{query}",
            "https": f"https://t.me/proxy?{query}",
        })

    # ---- server --------------------------------------------------------

    def server_status(self) -> Response:
        uptime = float((self.proc_root / "uptime").read_text().split()[0])
        load = (self.proc_root / "loadavg").read_text().split()[:3]
        mem = parse_meminfo((self.proc_root / "meminfo").read_text())
        disk = shutil.disk_usage("/")
        rc, out, _ = self._docker("ps", "-a", "--format", "{{.Names}}\t{{.Status}}")
        containers = []
        if rc == 0:
            for line in out.strip().splitlines():
                cname, _, status = line.partition("\t")
                containers.append({"name": cname, "status": status})
        return Response.json({
            "uptime_seconds": int(uptime),
            "load": [float(x) for x in load],
            "mem_total": mem.get("MemTotal", 0),
            "mem_available": mem.get("MemAvailable", 0),
            "disk_total": disk.total,
            "disk_free": disk.free,
            "containers": containers,
            "time": int(time.time()),
        })

    # ---- service health ------------------------------------------------

    def _check_awg(self) -> dict:
        iface = self.config.awg_iface
        rc, out, err = self.runner(["awg", "show", iface, "latest-handshakes"], 15)
        if rc != 0:
            return {"name": f"AmneziaWG ({iface})", "kind": "vpn", "ok": False,
                    "detail": _tail(err or out, 2) or "интерфейс не поднят"}
        now = time.time()
        stamps = [int(p[1]) for p in (line.split() for line in out.splitlines()) if len(p) == 2 and p[1].isdigit()]
        online = sum(1 for ts in stamps if ts and now - ts < 180)
        return {"name": f"AmneziaWG ({iface})", "kind": "vpn", "ok": True,
                "detail": f"клиентов {len(stamps)}, онлайн {online}"}

    def _check_unit(self, unit: str) -> dict:
        rc, out, _ = self.runner(["systemctl", "is-active", unit], 10)
        state = out.strip() or "unknown"
        return {"name": unit, "kind": "systemd", "ok": rc == 0 and state == "active", "detail": state}

    def _check_container(self, name: str) -> dict:
        rc, out, err = self._docker("inspect", "--format", "{{json .State}}", name, timeout=15)
        if rc != 0:
            return {"name": name, "kind": "docker", "ok": False, "detail": "контейнер не найден"}
        state = json.loads(out)
        health = (state.get("Health") or {}).get("Status")
        ok = bool(state.get("Running")) and health in (None, "healthy", "starting")
        detail = state.get("Status") or "?"
        if health:
            detail += f", {health}"
        if state.get("RestartCount"):
            detail += f", перезапусков {state['RestartCount']}"
        return {"name": name, "kind": "docker", "ok": ok, "detail": detail}

    def _check_tcp(self, label: str, host: str, port: int) -> dict:
        ok = self.tcp_probe(host, port)
        return {"name": label, "kind": "port", "ok": ok, "detail": "отвечает" if ok else "не отвечает"}

    def services(self) -> Response:
        checks = [self._check_awg()]
        checks += [self._check_container(c) for c in self.config.containers]
        checks += [self._check_tcp(*t) for t in self.config.tcp_checks]
        checks += [self._check_unit(u) for u in self.config.units]
        return Response.json({"services": checks, "ok": all(c["ok"] for c in checks)})

    # ---- routing -------------------------------------------------------

    def authorized(self, header: str | None) -> bool:
        if not header or not header.startswith("Bearer "):
            return False
        return hmac.compare_digest(header[7:].encode(), self.config.token.encode())

    def dispatch(self, method: str, path: str, body: dict | None = None) -> Response:
        parts = [unquote(p) for p in urlsplit(path).path.strip("/").split("/") if p]
        body = body or {}
        route = (method, *parts)
        match route:
            case ("GET", "health"):
                return Response.json({"ok": True})
            case ("GET", "awg", "clients"):
                return self.awg_list()
            case ("GET", "awg", "stats"):
                return self.awg_stats()
            case ("POST", "awg", "clients"):
                return self.awg_add(body)
            case ("DELETE", "awg", "clients", name):
                return self.awg_remove(name)
            case ("GET", "awg", "clients", name, "files", kind):
                return self.awg_file(name, kind)
            case ("GET", "proxy", "status"):
                return self.proxy_status()
            case ("POST", "proxy", "restart"):
                return self.proxy_restart()
            case ("GET", "proxy", "link"):
                return self.proxy_link()
            case ("GET", "server", "status"):
                return self.server_status()
            case ("GET", "services"):
                return self.services()
        raise ApiError(404, "Not found")

    def handle(self, method: str, path: str, auth: str | None, raw_body: bytes = b"") -> Response:
        """Full request handling: auth, body parsing, dispatch, error mapping."""
        if not self.authorized(auth):
            return Response.json({"error": "unauthorized"}, status=401)
        try:
            body = json.loads(raw_body) if raw_body else {}
            if not isinstance(body, dict):
                raise ApiError(400, "Тело запроса должно быть JSON-объектом")
            return self.dispatch(method, path, body)
        except json.JSONDecodeError:
            return Response.json({"error": "Некорректный JSON"}, status=400)
        except ApiError as e:
            return Response.json({"error": e.message}, status=e.status)
        except Exception:
            log.exception("Unhandled error on %s %s", method, path)
            return Response.json({"error": "Внутренняя ошибка агента"}, status=500)


def make_handler(agent: Agent) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ShishkaAgent/1.0"

        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                resp = Response.json({"error": "body too large"}, status=413)
            else:
                raw = self.rfile.read(length) if length else b""
                resp = agent.handle(self.command, self.path, self.headers.get("Authorization"), raw)
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.content_type)
            self.send_header("Content-Length", str(len(resp.body)))
            self.end_headers()
            self.wfile.write(resp.body)

        do_GET = do_POST = do_DELETE = _serve

        def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - stdlib name
            log.info("%s %s", self.address_string(), fmt % args)

    return Handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = AgentConfig.from_env()
    agent = Agent(config)
    server = ThreadingHTTPServer((config.bind, config.port), make_handler(agent))
    log.info("Listening on %s:%s", config.bind, config.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
