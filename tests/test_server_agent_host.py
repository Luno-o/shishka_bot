"""Host agent (server_agent/agent.py): auth, validation, whitelisted commands."""
import json
from pathlib import Path

import pytest

from server_agent.agent import Agent, AgentConfig, extract_mtg_secret, parse_meminfo

TOKEN = "t" * 32
AUTH = f"Bearer {TOKEN}"


class FakeRunner:
    """Records commands; answers from a script of (predicate, result) rules."""

    def __init__(self, awg_dir: Path):
        self.calls: list[list[str]] = []
        self.awg_dir = awg_dir
        self.responses: dict[str, tuple[int, str, str]] = {}

    def __call__(self, args, timeout):
        self.calls.append(list(args))
        if args[0] == "bash":
            cmd = [a for a in args[2:] if not a.startswith("--")]
            if cmd and cmd[0] == "add":
                (self.awg_dir / f"{cmd[1]}.conf").write_text("[Interface]\n")
            if cmd and cmd[0] == "remove":
                (self.awg_dir / f"{cmd[1]}.conf").unlink(missing_ok=True)
            return self.responses.get(cmd[0] if cmd else "", (0, "[]", ""))
        if args[0] in self.responses:  # per-binary override (awg, systemctl, docker ...)
            return self.responses[args[0]]
        if args[:2] == ["awg", "show"]:
            return 0, f"keyA\t{int(__import__('time').time())}\nkeyB\t0\n", ""
        if args[:2] == ["systemctl", "is-active"]:
            return 0, "active\n", ""
        if args[:2] == ["docker", "inspect"]:
            if "{{json .Args}}" in args:
                return 0, json.dumps(["simple-run", "0.0.0.0:3128", "ee0123456789abcdef0123456789abcdef6578616d706c652e636f6d"]), ""
            return 0, json.dumps({"Status": "running", "Running": True, "StartedAt": "x", "RestartCount": 0}), ""
        if args[:2] == ["docker", "restart"]:
            return 0, "mtproto-proxy\n", ""
        if args[:2] == ["docker", "ps"]:
            return 0, "shishka-bot\tUp 1 hour\nmtproto-proxy\tUp 2 hours\n", ""
        return 1, "", "unexpected"


@pytest.fixture
def agent(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "uptime").write_text("3600.5 100.0\n")
    (proc / "loadavg").write_text("0.10 0.20 0.30 1/100 123\n")
    (proc / "meminfo").write_text("MemTotal: 4000 kB\nMemAvailable: 2000 kB\n")
    awg = tmp_path / "awg"
    awg.mkdir()
    cfg = AgentConfig(token=TOKEN, awg_dir=awg, awg_manage=awg / "manage_amneziawg.sh", proxy_host="1.2.3.4")
    return Agent(cfg, runner=FakeRunner(awg), proc_root=proc, tcp_probe=lambda host, port: True)


def body(resp):
    return json.loads(resp.body)


def test_rejects_missing_or_wrong_token(agent):
    assert agent.handle("GET", "/health", None).status == 401
    assert agent.handle("GET", "/health", "Bearer nope").status == 401
    assert agent.handle("GET", "/health", TOKEN).status == 401
    assert agent.handle("GET", "/health", AUTH).status == 200


def test_unknown_route_is_404(agent):
    assert agent.handle("GET", "/etc/passwd", AUTH).status == 404
    assert agent.handle("POST", "/awg/stats", AUTH).status == 404


def test_config_requires_long_token():
    with pytest.raises(ValueError):
        AgentConfig.from_env({"AGENT_TOKEN": "short"})
    cfg = AgentConfig.from_env({"AGENT_TOKEN": TOKEN, "PROXY_HOST": "h", "AWG_DIR": "/x"})
    assert cfg.awg_manage == Path("/x/manage_amneziawg.sh")
    assert cfg.bind == "172.17.0.1"


def test_list_calls_script_with_json(agent):
    agent.runner.responses["list"] = (0, json.dumps([{"name": "mom"}]), "")
    resp = agent.handle("GET", "/awg/clients", AUTH)
    assert resp.status == 200
    assert body(resp) == {"clients": [{"name": "mom"}]}
    assert agent.runner.calls[-1][-2:] == ["--json", "list"]
    assert "--no-color" in agent.runner.calls[-1]


def test_list_non_json_output_is_502(agent):
    agent.runner.responses["list"] = (0, "not json", "")
    assert agent.handle("GET", "/awg/clients", AUTH).status == 502


@pytest.mark.parametrize("name", ["", "a b", "x;rm -rf /", "../etc", "-rf", "a" * 33, "имя"])
def test_add_rejects_bad_names(agent, name):
    resp = agent.handle("POST", "/awg/clients", AUTH, json.dumps({"name": name}).encode())
    assert resp.status == 400
    assert not any(c[0] == "bash" for c in agent.runner.calls)


@pytest.mark.parametrize("expires", ["0d", "7", "7x", "1000d", "7d; ls"])
def test_add_rejects_bad_expiry(agent, expires):
    resp = agent.handle("POST", "/awg/clients", AUTH, json.dumps({"name": "ok", "expires": expires}).encode())
    assert resp.status == 400


def test_add_passes_yes_and_expiry(agent):
    resp = agent.handle("POST", "/awg/clients", AUTH, json.dumps({"name": "guest_1", "expires": "7d"}).encode())
    assert resp.status == 201
    call = agent.runner.calls[-1]
    assert call[-2:] == ["add", "guest_1"]
    assert "--yes" in call and "--expires=7d" in call


def test_add_existing_client_is_409(agent):
    (agent.config.awg_dir / "mom.conf").write_text("x")
    resp = agent.handle("POST", "/awg/clients", AUTH, json.dumps({"name": "mom"}).encode())
    assert resp.status == 409


def test_add_script_failure_is_502(agent):
    agent.runner.responses["add"] = (1, "", "boom")
    agent.runner.awg_dir = agent.config.awg_dir / "nowhere"  # script "fails" and creates nothing
    agent.runner.awg_dir.mkdir()
    resp = agent.handle("POST", "/awg/clients", AUTH, json.dumps({"name": "x"}).encode())
    assert resp.status == 502
    assert "boom" in body(resp)["error"]


def test_remove(agent):
    (agent.config.awg_dir / "guest.conf").write_text("x")
    resp = agent.handle("DELETE", "/awg/clients/guest", AUTH)
    assert resp.status == 200
    assert agent.runner.calls[-1][-3:] == ["--yes", "remove", "guest"]


def test_remove_missing_is_404(agent):
    assert agent.handle("DELETE", "/awg/clients/ghost", AUTH).status == 404


def test_remove_rejects_traversal(agent):
    assert agent.handle("DELETE", "/awg/clients/..%2Fx", AUTH).status == 400


def test_file_download(agent):
    (agent.config.awg_dir / "mom.conf").write_text("[Interface]")
    (agent.config.awg_dir / "mom.vpnuri.png").write_bytes(b"\x89PNG")
    resp = agent.handle("GET", "/awg/clients/mom/files/conf", AUTH)
    assert resp.status == 200 and resp.body == b"[Interface]"
    resp = agent.handle("GET", "/awg/clients/mom/files/vpnuri_qr", AUTH)
    assert resp.content_type == "image/png"
    assert agent.handle("GET", "/awg/clients/mom/files/private", AUTH).status == 404
    assert agent.handle("GET", "/awg/clients/mom/files/qr", AUTH).status == 404


def test_proxy_restart_and_status(agent):
    resp = agent.handle("POST", "/proxy/restart", AUTH)
    assert resp.status == 200
    assert body(resp)["running"] is True
    assert ["docker", "restart", "mtproto-proxy"] in agent.runner.calls


def test_proxy_link(agent):
    data = body(agent.handle("GET", "/proxy/link", AUTH))
    assert data["tg"].startswith("tg://proxy?server=1.2.3.4&port=443&secret=ee0123")


def test_proxy_link_needs_host(agent):
    agent.config.proxy_host = ""
    assert agent.handle("GET", "/proxy/link", AUTH).status == 503


def test_server_status(agent):
    data = body(agent.handle("GET", "/server/status", AUTH))
    assert data["uptime_seconds"] == 3600
    assert data["load"] == [0.1, 0.2, 0.3]
    assert data["mem_total"] == 4000 * 1024
    assert {"name": "mtproto-proxy", "status": "Up 2 hours"} in data["containers"]


def test_bad_json_body(agent):
    assert agent.handle("POST", "/awg/clients", AUTH, b"{nope").status == 400
    assert agent.handle("POST", "/awg/clients", AUTH, b"[1]").status == 400


def test_extract_secret():
    assert extract_mtg_secret(["simple-run", "-n", "1.1.1.1", "0.0.0.0:3128", "ee" + "ab" * 20]) == "ee" + "ab" * 20
    assert extract_mtg_secret(["simple-run", "0.0.0.0:3128"]) is None


def test_parse_meminfo():
    assert parse_meminfo("MemTotal: 2 kB\nBad line\n") == {"MemTotal": 2048}


def test_http_roundtrip(agent):
    """The real HTTP layer: headers, body limit and status codes reach the client."""
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    from server_agent.agent import make_handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(agent))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        req = urllib.request.Request(f"{base}/health", headers={"Authorization": AUTH})
        with urllib.request.urlopen(req) as r:
            assert json.loads(r.read()) == {"ok": True}

        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"{base}/health")
        assert e.value.code == 401

        req = urllib.request.Request(
            f"{base}/awg/clients", data=b"x" * 5000, method="POST", headers={"Authorization": AUTH}
        )
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        assert e.value.code == 413
    finally:
        server.shutdown()


def test_services_all_ok(agent):
    data = body(agent.handle("GET", "/services", AUTH))
    assert data["ok"] is True
    names = [c["name"] for c in data["services"]]
    assert names[0].startswith("AmneziaWG") and "shishka-bot" in names and "docker" in names
    assert "MTProto :443" in names
    assert data["services"][0]["detail"] == "клиентов 2, онлайн 1"


def test_services_report_failures(agent):
    agent.runner.responses["awg"] = (1, "", "Unable to access interface: No such device")
    agent.runner.responses["systemctl"] = (3, "inactive\n", "")
    agent.tcp_probe = lambda host, port: False
    data = body(agent.handle("GET", "/services", AUTH))
    assert data["ok"] is False
    by_name = {c["name"]: c for c in data["services"]}
    assert by_name["AmneziaWG (awg0)"]["ok"] is False and "No such device" in by_name["AmneziaWG (awg0)"]["detail"]
    assert by_name["fail2ban"] == {"name": "fail2ban", "kind": "systemd", "ok": False, "detail": "inactive"}
    assert by_name["MTProto :443"]["ok"] is False


def test_services_unhealthy_or_missing_container(agent):
    def runner(args, timeout):
        if args[:2] == ["docker", "inspect"] and "shishka-bot" in args:
            return 0, json.dumps({"Status": "running", "Running": True, "Health": {"Status": "unhealthy"}}), ""
        if args[:2] == ["docker", "inspect"] and "mtproto-proxy" in args:
            return 1, "", "No such object"
        return FakeRunner(agent.config.awg_dir)(args, timeout)

    agent.runner = runner
    by_name = {c["name"]: c for c in body(agent.handle("GET", "/services", AUTH))["services"]}
    assert by_name["shishka-bot"]["ok"] is False and "unhealthy" in by_name["shishka-bot"]["detail"]
    assert by_name["mtproto-proxy"] == {"name": "mtproto-proxy", "kind": "docker", "ok": False,
                                        "detail": "контейнер не найден"}


def test_config_check_lists_from_env():
    cfg = AgentConfig.from_env({"AGENT_TOKEN": TOKEN, "CHECK_UNITS": "docker, cron", "CHECK_TCP": "Bot:127.0.0.1:8081"})
    assert cfg.units == ("docker", "cron")
    assert cfg.tcp_checks == (("Bot :8081", "127.0.0.1", 8081),)
