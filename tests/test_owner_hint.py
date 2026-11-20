"""Owner-only commands sent anonymously get a hint instead of silence."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.filters import Command

from handlers import personal_actions

CHAT_ID = -100500


def _message(sender_chat):
    msg = MagicMock()
    msg.chat = SimpleNamespace(id=CHAT_ID, type="supergroup")
    msg.from_user = SimpleNamespace(id=1087968824)
    msg.sender_chat = sender_chat
    msg.is_automatic_forward = None
    msg.reply = AsyncMock(return_value=MagicMock())
    msg.answer = AsyncMock(return_value=MagicMock())
    msg.delete = AsyncMock()
    return msg


@pytest.fixture(autouse=True)
def no_timers(monkeypatch):
    monkeypatch.setattr(personal_actions, "make_ephemeral", lambda *a, **k: None)


@pytest.mark.asyncio
async def test_anonymous_admin_gets_hint():
    msg = _message(SimpleNamespace(id=CHAT_ID))

    await personal_actions.owner_command_hint(msg)

    sent = (msg.answer.await_args or msg.reply.await_args).args[0]
    assert "личк" in sent and "аноним" in sent


@pytest.mark.asyncio
async def test_foreign_channel_gets_nothing():
    msg = _message(SimpleNamespace(id=-100999))

    await personal_actions.owner_command_hint(msg)

    msg.answer.assert_not_awaited()
    msg.reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_regular_member_gets_nothing():
    msg = _message(None)
    msg.from_user = SimpleNamespace(id=12345)

    await personal_actions.owner_command_hint(msg)

    msg.answer.assert_not_awaited()
    msg.reply.assert_not_awaited()


def test_hint_covers_every_owner_command():
    names: set[str] = set()
    for h in personal_actions.router.message.handlers:
        if h.callback is personal_actions.owner_command_hint:
            for f in h.filters or []:
                if isinstance(f.callback, Command):
                    names.update(f.callback.commands)
    assert {"metrics", "log", "chatid", "msg", "backup_now", "backup", "reload",
            "top_violators_spam", "top_violators_profanity"} <= names


@pytest.mark.parametrize("is_owner", [True, False], ids=["owner", "not-owner"])
@pytest.mark.asyncio
async def test_myid_in_private_shows_id_and_owner_status(monkeypatch, is_owner):
    from config import config

    monkeypatch.setattr(config.bot, "owner", 777 if is_owner else 1)
    msg = MagicMock()
    msg.chat = SimpleNamespace(id=777, type="private")
    msg.from_user = SimpleNamespace(id=777)
    msg.sender_chat = None
    msg.reply = AsyncMock()

    await personal_actions.cmd_my_id(msg)

    text = msg.reply.await_args.args[0]
    assert "777" in text
    assert ("владелец" in text.lower()) is True
    assert ("не владелец" in text.lower()) is (not is_owner)
    assert "1" not in text.replace("777", "")  # never reveals the configured owner id
