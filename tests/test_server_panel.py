"""Owner server panel: argument parsing, formatting and handler routing (agent mocked)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services import server_agent as sa


# ---- parsing ---------------------------------------------------------------

def test_parse_add_args():
    assert sa.parse_add_args("guest") == ("guest", None)
    assert sa.parse_add_args("guest_1 7D") == ("guest_1", "7d")


@pytest.mark.parametrize("text", [None, "", "a b c", "-rf", "имя", "x;y", "guest 7", "guest 0d", "a" * 33])
def test_parse_add_args_rejects(text):
    with pytest.raises(ValueError):
        sa.parse_add_args(text)


def test_parse_name_arg():
    assert sa.parse_name_arg(" mom ") == "mom"
    with pytest.raises(ValueError):
        sa.parse_name_arg("../x")


# ---- formatting ------------------------------------------------------------

def test_human_bytes_and_duration():
    assert sa.human_bytes(512) == "512 Б"
    assert sa.human_bytes(1536) == "1.5 КБ"
    assert sa.human_bytes(None) == "0 Б"
    assert sa.human_duration(90061) == "1 д 1 ч"
    assert sa.human_duration(3700) == "1 ч 1 мин"


def test_merge_stats_and_card():
    clients = [{"name": "mom", "ip": "10.9.9.2", "status_code": "active"}, {"name": "router"}]
    stats = [{"name": "mom", "rx": 2048, "tx": 1024, "last_handshake": 0, "ip": "ignored"}]
    merged = sa.merge_stats(clients, stats)
    assert merged[0]["rx"] == 2048 and merged[0]["ip"] == "10.9.9.2"
    assert merged[1] == {"name": "router"}
    card = sa.format_client(merged[0])
    assert "mom" in card and "10.9.9.2" in card and "2.0 КБ" in card and "Рукопожатие: нет" in card


def test_format_clients_escapes_html():
    text = sa.format_clients([{"name": "<b>x", "status_code": "active"}])
    assert "&lt;b&gt;x" in text and "🟢" in text
    assert "Клиентов нет" in sa.format_clients([])


def test_format_server_status():
    text = sa.format_server_status({
        "uptime_seconds": 7200, "load": [0.1, 0.2, 0.3], "mem_total": 4 * 2**30, "mem_available": 2 * 2**30,
        "disk_total": 30 * 2**30, "disk_free": 20 * 2**30,
        "containers": [{"name": "mtproto-proxy", "status": "Up 2 hours"}, {"name": "x", "status": "Exited (1)"}],
    })
    assert "2 ч 0 мин" in text and "2.0 ГБ / 4.0 ГБ" in text
    assert "🟢 mtproto-proxy" in text and "🔴 x" in text


def test_error_message():
    assert "токен" in sa.error_message(401, b"{}")
    assert sa.error_message(409, '{"error": "Клиент mom уже существует"}'.encode()) == "Клиент mom уже существует"
    assert sa.error_message(500, b"oops") == "Агент ответил ошибкой 500"


def test_format_services_groups_and_summary():
    text = sa.format_services({"ok": False, "services": [
        {"name": "AmneziaWG (awg0)", "kind": "vpn", "ok": True, "detail": "клиентов 7, онлайн 2"},
        {"name": "mtproto-proxy", "kind": "docker", "ok": False, "detail": "exited"},
        {"name": "docker", "kind": "systemd", "ok": True, "detail": "active"},
    ]})
    assert "Не работает: 1 из 3" in text
    assert "🟢 AmneziaWG (awg0): клиентов 7, онлайн 2" in text
    assert "🔴 mtproto-proxy: exited" in text
    assert text.index("<b>VPN</b>") < text.index("<b>Контейнеры</b>") < text.index("<b>Системные службы</b>")
    assert "Всё работает" in sa.format_services({"services": [{"name": "x", "kind": "vpn", "ok": True}]})


def test_format_services_agent_down():
    text = sa.format_services(None, "Агент сервера недоступен: ClientConnectorError")
    assert "🟢 Бот" in text and "🔴 Агент сервера" in text and "shishka-agent" in text


@pytest.mark.asyncio
async def test_client_without_config_raises():
    client = sa.ServerAgentClient(base_url="", token="")
    with pytest.raises(sa.ServerAgentError):
        await client.server_status()


# ---- handlers --------------------------------------------------------------

@pytest.fixture
def panel(monkeypatch):
    from handlers import server_admin

    fake = MagicMock()
    fake.awg_clients = AsyncMock(return_value=[{"name": "mom"}, {"name": "router"}])
    fake.awg_stats = AsyncMock(return_value=[])
    fake.awg_add = AsyncMock(return_value={"ok": True})
    fake.awg_remove = AsyncMock(return_value={"ok": True})
    fake.awg_file = AsyncMock(side_effect=lambda name, kind: b"vpn://abc" if kind == "vpnuri" else b"\x89PNG")
    fake.proxy_status = AsyncMock(return_value={"container": "mtproto-proxy", "status": "running", "running": True})
    fake.proxy_restart = AsyncMock(return_value={"container": "mtproto-proxy", "status": "running", "running": True})
    fake.services = AsyncMock(return_value={"ok": True, "services": [
        {"name": "mtproto-proxy", "kind": "docker", "ok": True, "detail": "running"}]})
    fake.proxy_link = AsyncMock(return_value={"https": "https://t.me/proxy?server=h", "tg": "tg://proxy?server=h"})
    monkeypatch.setattr(server_admin, "get_client", lambda: fake)
    return server_admin, fake


def _call(data):
    call = MagicMock()
    call.data = data
    call.answer = AsyncMock()
    call.message = MagicMock()
    call.message.edit_text = AsyncMock()
    call.message.answer = AsyncMock()
    call.message.answer_photo = AsyncMock()
    call.message.answer_document = AsyncMock()
    return call


def _message():
    msg = MagicMock()
    status = MagicMock()
    status.edit_text = AsyncMock()
    msg.answer = AsyncMock(return_value=status)
    msg.answer_photo = AsyncMock()
    msg.answer_document = AsyncMock()
    return msg, status


def _buttons(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


@pytest.mark.asyncio
async def test_vpn_list_shows_client_buttons(panel):
    server_admin, _ = panel
    call = _call("srv:awg")
    await server_admin.on_server_callback(call)
    markup = call.message.edit_text.await_args.kwargs["reply_markup"]
    assert "srv:c:mom" in _buttons(markup) and "srv:c:router" in _buttons(markup)
    call.answer.assert_awaited()


@pytest.mark.asyncio
async def test_delete_needs_confirmation(panel):
    server_admin, fake = panel
    call = _call("srv:d:mom")
    await server_admin.on_server_callback(call)
    fake.awg_remove.assert_not_awaited()
    assert "srv:dy:mom" in _buttons(call.message.edit_text.await_args.kwargs["reply_markup"])

    await server_admin.on_server_callback(_call("srv:dy:mom"))
    fake.awg_remove.assert_awaited_once_with("mom")


@pytest.mark.asyncio
async def test_restart_needs_confirmation(panel):
    server_admin, fake = panel
    await server_admin.on_server_callback(_call("srv:pr"))
    fake.proxy_restart.assert_not_awaited()
    await server_admin.on_server_callback(_call("srv:pry"))
    fake.proxy_restart.assert_awaited_once()


@pytest.mark.asyncio
async def test_bad_callback_name_is_rejected(panel):
    server_admin, fake = panel
    call = _call("srv:dy:../etc")
    await server_admin.on_server_callback(call)
    fake.awg_remove.assert_not_awaited()
    assert call.answer.await_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_agent_error_becomes_alert(panel):
    server_admin, fake = panel
    fake.proxy_status.side_effect = sa.ServerAgentError("Агент сервера недоступен")
    call = _call("srv:proxy")
    await server_admin.on_server_callback(call)
    assert "недоступен" in call.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_vpn_add_issues_key_and_sends_amnezia_link(panel):
    server_admin, fake = panel
    msg, status = _message()
    await server_admin.cmd_vpn_add(msg, SimpleNamespace(args="guest 7d"))
    fake.awg_add.assert_awaited_once_with("guest", "7d")
    assert "выпущен" in status.edit_text.await_args.args[0]
    assert any("vpn://abc" in c.args[0] for c in msg.answer.await_args_list)
    msg.answer_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_vpn_add_bad_args_does_not_call_agent(panel):
    server_admin, fake = panel
    msg, _ = _message()
    await server_admin.cmd_vpn_add(msg, SimpleNamespace(args="-rf"))
    fake.awg_add.assert_not_awaited()


@pytest.mark.asyncio
async def test_vpn_add_agent_error_is_shown(panel):
    server_admin, fake = panel
    fake.awg_add.side_effect = sa.ServerAgentError("Клиент guest уже существует")
    msg, status = _message()
    await server_admin.cmd_vpn_add(msg, SimpleNamespace(args="guest"))
    assert "уже существует" in status.edit_text.await_args.args[0]


def test_router_is_owner_and_private_only():
    from handlers import server_admin
    from filters import IsOwnerFilter

    message_filters = [f.callback for f in server_admin.router.message._handler.filters or []]
    callback_filters = [f.callback for f in server_admin.router.callback_query._handler.filters or []]
    assert any(isinstance(f, IsOwnerFilter) for f in message_filters)
    assert any(isinstance(f, IsOwnerFilter) for f in callback_filters)
    assert len(message_filters) >= 2  # owner + private chat


def test_panel_router_registered_before_owner_hint():
    from aiogram import Dispatcher

    from handlers import register_all_handlers

    dp = Dispatcher()
    register_all_handlers(dp)
    names = [r.name for r in dp.sub_routers]
    assert names.index("server_admin") < names.index("personal_actions")


@pytest.mark.asyncio
async def test_status_command(panel):
    server_admin, _ = panel
    msg, _ = _message()
    await server_admin.cmd_status(msg)
    text = msg.answer.await_args.args[0]
    assert "Всё работает" in text and "mtproto-proxy" in text


@pytest.mark.asyncio
async def test_status_command_when_agent_down(panel):
    server_admin, fake = panel
    fake.services.side_effect = sa.ServerAgentError("Агент сервера недоступен: ClientConnectorError")
    msg, _ = _message()
    await server_admin.cmd_status(msg)
    assert "🔴 Агент сервера" in msg.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_services_button(panel):
    server_admin, _ = panel
    call = _call("srv:svc")
    await server_admin.on_server_callback(call)
    assert "mtproto-proxy" in call.message.edit_text.await_args.args[0]
