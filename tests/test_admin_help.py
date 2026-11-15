from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError

from config import config
from handlers import admin_actions

CHAT_ID = -100500
ADMIN_ID = 42
LOGS_ID = -5530194627


def _message(*, sender_chat=None, from_id=ADMIN_ID):
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=SimpleNamespace(chat=SimpleNamespace(id=0), message_id=7))
    msg = MagicMock()
    msg.bot = bot
    msg.chat = SimpleNamespace(id=CHAT_ID, type="supergroup", title="Чат")
    msg.from_user = SimpleNamespace(id=from_id)
    msg.sender_chat = sender_chat
    msg.delete = AsyncMock()
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg


@pytest.fixture
def env(monkeypatch):
    scheduled = []
    monkeypatch.setattr(config.groups, "logs", LOGS_ID)
    monkeypatch.setattr(
        admin_actions, "schedule_delete",
        lambda bot, chat_id, message_id, delay: scheduled.append((chat_id, message_id, delay)),
    )
    return scheduled


def _admin(monkeypatch, is_admin: bool):
    monkeypatch.setattr(admin_actions, "is_admin_sender", AsyncMock(return_value=is_admin))


@pytest.mark.asyncio
async def test_non_admin_trigger_deleted_and_nothing_sent(monkeypatch, env):
    _admin(monkeypatch, False)
    msg = _message()

    await admin_actions.cmd_admin_help(msg)

    msg.delete.assert_awaited_once()
    msg.bot.send_message.assert_not_awaited()
    msg.reply.assert_not_awaited()
    msg.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_gets_help_in_private_and_it_expires(monkeypatch, env):
    _admin(monkeypatch, True)
    msg = _message()

    await admin_actions.cmd_admin_help(msg)

    msg.delete.assert_awaited_once()
    targets = [c.args[0] for c in msg.bot.send_message.await_args_list]
    assert targets and set(targets) == {ADMIN_ID}
    assert CHAT_ID not in targets
    msg.reply.assert_not_awaited()
    assert env and all(delay == config.ephemeral.admin_help_ttl for _, _, delay in env)


@pytest.mark.asyncio
async def test_closed_private_chat_falls_back_to_logs(monkeypatch, env):
    _admin(monkeypatch, True)
    msg = _message()
    calls = []

    async def send(chat_id, text, **kw):
        calls.append(chat_id)
        if chat_id == ADMIN_ID:
            raise TelegramForbiddenError(method=MagicMock(), message="bot can't initiate conversation")
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=8)

    msg.bot.send_message = AsyncMock(side_effect=send)

    await admin_actions.cmd_admin_help(msg)

    assert LOGS_ID in calls
    assert CHAT_ID not in calls
    assert env


@pytest.mark.parametrize(
    "sender_chat",
    [SimpleNamespace(id=CHAT_ID), SimpleNamespace(id=-100777)],
    ids=["anonymous-admin", "linked-channel"],
)
@pytest.mark.asyncio
async def test_chat_or_channel_sender_gets_help_in_logs(monkeypatch, env, sender_chat):
    _admin(monkeypatch, True)
    msg = _message(sender_chat=sender_chat, from_id=1087968824)

    await admin_actions.cmd_admin_help(msg)

    targets = {c.args[0] for c in msg.bot.send_message.await_args_list}
    assert targets == {LOGS_ID}
    msg.reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_logs_chat_configured_sends_nothing_to_group(monkeypatch, env):
    _admin(monkeypatch, True)
    monkeypatch.setattr(config.groups, "logs", 0)
    msg = _message(sender_chat=SimpleNamespace(id=CHAT_ID), from_id=1087968824)

    await admin_actions.cmd_admin_help(msg)

    msg.delete.assert_awaited_once()
    msg.bot.send_message.assert_not_awaited()
    msg.reply.assert_not_awaited()


def test_admin_help_chunks_fit_message_limit():
    from utils.text_split import MESSAGE_LIMIT, visible_length

    chunks = admin_actions.admin_help_chunks()
    assert chunks
    assert all(visible_length(c) <= MESSAGE_LIMIT for c in chunks)
    assert "Правило" in "".join(chunks)
