"""
Owner-only server panel in the bot's private chat: AmneziaWG keys, MTProto
proxy restart and server status, via the host agent (server_agent/agent.py).

Commands (private chat, owner only):
    !server / !сервер          - panel with buttons
    !status / !статус          - what works and what does not
    !vpn_add <имя> [срок]      - issue a VPN key (срок: 12h, 7d, 4w ...)
    !vpn_del <имя>             - revoke a VPN key (asks for confirmation)

Callback data: "srv:<action>[:<arg>...]", all handled here.
"""
import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from filters import IsOwnerFilter
from services.server_agent import (
    ServerAgentClient,
    ServerAgentError,
    find_client,
    format_client,
    format_clients,
    format_proxy_status,
    format_server_status,
    format_services,
    merge_stats,
    parse_add_args,
    parse_name_arg,
)

router = Router(name="server_admin")
logger = logging.getLogger(__name__)

PRIVATE = F.chat.type == "private"

# Router-level guard: nothing here runs for anyone but the owner.
router.message.filter(IsOwnerFilter(), PRIVATE)
router.callback_query.filter(IsOwnerFilter(), F.data.startswith("srv:"))


def get_client() -> ServerAgentClient:
    """Indirection so tests can swap the client."""
    return ServerAgentClient()


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


BACK_TO_MENU = _btn("⬅️ Меню", "srv:menu")


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📊 Сервисы", "srv:svc"), _btn("🖥 Ресурсы", "srv:status")],
        [_btn("🔐 VPN-ключи", "srv:awg"), _btn("📡 Прокси", "srv:proxy")],
    ])


def clients_keyboard(names: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(names), 2):
        rows.append([_btn(n, f"srv:c:{n}") for n in names[i:i + 2]])
    rows.append([_btn("🔄 Обновить", "srv:awg"), BACK_TO_MENU])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def client_keyboard(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📱 Для Amnezia", f"srv:f:uri:{name}"), _btn("📄 .conf + QR", f"srv:f:conf:{name}")],
        [_btn("🗑 Отозвать ключ", f"srv:d:{name}")],
        [_btn("⬅️ К списку", "srv:awg")],
    ])


def confirm_delete_keyboard(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(f"✅ Да, отозвать {name}", f"srv:dy:{name}")],
        [_btn("Отмена", f"srv:c:{name}")],
    ])


def proxy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔁 Перезапустить", "srv:pr"), _btn("🔗 Ссылка", "srv:pl")],
        [_btn("🔄 Обновить", "srv:proxy"), BACK_TO_MENU],
    ])


def confirm_restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ Да, перезапустить", "srv:pry")],
        [_btn("Отмена", "srv:proxy")],
    ])


MENU_TEXT = "🛠 <b>Панель сервера</b>\nВыберите раздел."


async def _edit(call: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup | None) -> None:
    try:
        await call.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        # "message is not modified" after a refresh with identical content
        if "not modified" not in str(e):
            raise


async def send_client_files(message: Message, name: str, kind: str) -> None:
    """kind 'uri': vpn:// link + its QR (Amnezia apps); 'conf': .conf file + its QR."""
    client = get_client()
    if kind == "uri":
        uri = (await client.awg_file(name, "vpnuri")).decode().strip()
        await message.answer(
            f"📱 <b>{html.escape(name)}</b>: ключ для AmneziaVPN / AmneziaWG\n<code>{html.escape(uri)}</code>"
        )
        qr = await client.awg_file(name, "vpnuri_qr")
    else:
        conf = await client.awg_file(name, "conf")
        await message.answer_document(BufferedInputFile(conf, filename=f"{name}.conf"))
        qr = await client.awg_file(name, "qr")
    await message.answer_photo(BufferedInputFile(qr, filename=f"{name}.png"), caption=f"QR: {name}")


async def _show_clients(call: CallbackQuery) -> None:
    client = get_client()
    clients = await client.awg_clients()
    names = sorted(str(c.get("name")) for c in clients if c.get("name"))
    await _edit(call, format_clients(clients), clients_keyboard(names))


async def _show_client(call: CallbackQuery, name: str) -> None:
    client = get_client()
    clients = await client.awg_clients()
    try:
        clients = merge_stats(clients, await client.awg_stats())
    except ServerAgentError:
        pass  # stats are optional decoration
    found = find_client(clients, name)
    if found is None:
        await _edit(call, f"Клиент <code>{html.escape(name)}</code> не найден.", clients_keyboard([]))
        return
    await _edit(call, format_client(found), client_keyboard(name))


SERVICES_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[[_btn("🔄 Обновить", "srv:svc"), BACK_TO_MENU]])


async def services_text() -> str:
    try:
        return format_services(await get_client().services())
    except ServerAgentError as e:
        return format_services(None, str(e))


### COMMANDS ###


@router.message(Command("status", "статус", prefix="!/"))
async def cmd_status(message: Message) -> None:
    await message.answer(await services_text(), reply_markup=SERVICES_KEYBOARD)



@router.message(Command("server", "сервер", prefix="!/"))
async def cmd_server(message: Message) -> None:
    await message.answer(MENU_TEXT, reply_markup=menu_keyboard())


@router.message(Command("vpn_add", prefix="!/"))
async def cmd_vpn_add(message: Message, command: CommandObject) -> None:
    try:
        name, expires = parse_add_args(command.args)
    except ValueError as e:
        await message.answer(str(e))
        return
    status = await message.answer(f"⏳ Выпускаю ключ <code>{html.escape(name)}</code>…")
    try:
        await get_client().awg_add(name, expires)
        suffix = f", срок {expires}" if expires else ""
        await status.edit_text(f"✅ Ключ <code>{html.escape(name)}</code> выпущен{suffix}.")
        await send_client_files(message, name, "uri")
        await message.answer("Карточка клиента:", reply_markup=client_keyboard(name))
    except ServerAgentError as e:
        await status.edit_text(f"❌ {html.escape(str(e))}")


@router.message(Command("vpn_del", prefix="!/"))
async def cmd_vpn_del(message: Message, command: CommandObject) -> None:
    try:
        name = parse_name_arg(command.args)
    except ValueError as e:
        await message.answer(str(e))
        return
    await message.answer(
        f"Отозвать ключ <code>{html.escape(name)}</code>? Устройство потеряет доступ к VPN.",
        reply_markup=confirm_delete_keyboard(name),
    )


### CALLBACKS ###


@router.callback_query()
async def on_server_callback(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    action, args = parts[1], parts[2:]
    try:
        await _route(call, action, args)
    except ServerAgentError as e:
        await call.answer(str(e)[:200], show_alert=True)
        return
    except (IndexError, ValueError):
        logger.warning("Malformed server panel callback: %r", call.data)
        await call.answer("❌ Ошибка данных", show_alert=True)
        return
    await call.answer()


async def _route(call: CallbackQuery, action: str, args: list[str]) -> None:
    client = get_client()
    match action, args:
        case "menu", []:
            await _edit(call, MENU_TEXT, menu_keyboard())
        case "svc", []:
            await _edit(call, await services_text(), SERVICES_KEYBOARD)
        case "status", []:
            await _edit(call, format_server_status(await client.server_status()),
                        InlineKeyboardMarkup(inline_keyboard=[[_btn("🔄 Обновить", "srv:status"), BACK_TO_MENU]]))
        case "awg", []:
            await _show_clients(call)
        case "c", [name]:
            await _show_client(call, parse_name_arg(name))
        case "f", [kind, name] if kind in ("uri", "conf"):
            await send_client_files(call.message, parse_name_arg(name), kind)
        case "d", [name]:
            name = parse_name_arg(name)
            await _edit(call, f"Отозвать ключ <code>{html.escape(name)}</code>? "
                              "Устройство потеряет доступ к VPN.", confirm_delete_keyboard(name))
        case "dy", [name]:
            name = parse_name_arg(name)
            await client.awg_remove(name)
            await call.message.answer(f"🗑 Ключ <code>{html.escape(name)}</code> отозван.")
            await _show_clients(call)
        case "proxy", []:
            await _edit(call, format_proxy_status(await client.proxy_status()), proxy_keyboard())
        case "pr", []:
            await _edit(call, "Перезапустить MTProto-прокси? Подключения оборвутся на несколько секунд.",
                        confirm_restart_keyboard())
        case "pry", []:
            await _edit(call, "⏳ Перезапускаю прокси…", None)
            try:
                status = await client.proxy_restart()
            except ServerAgentError as e:
                await _edit(call, f"❌ {html.escape(str(e))}", proxy_keyboard())
                raise
            await _edit(call, "✅ Перезапущено.\n\n" + format_proxy_status(status), proxy_keyboard())
        case "pl", []:
            link = await client.proxy_link()
            await call.message.answer(f"🔗 Прокси:\n{html.escape(link['https'])}")
        case _:
            raise ValueError(action)
