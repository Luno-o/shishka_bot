import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import ephemeral


def _chat(chat_type: str):
    return SimpleNamespace(type=chat_type, id=-100123)


def _sent_message(chat_type: str = "supergroup", message_id: int = 42):
    return SimpleNamespace(
        bot=SimpleNamespace(delete_message=AsyncMock()),
        chat=_chat(chat_type),
        message_id=message_id,
    )


def _trigger_message(chat_type: str = "supergroup"):
    return SimpleNamespace(chat=_chat(chat_type), delete=AsyncMock())


@pytest.mark.asyncio
async def test_make_ephemeral_schedules_delete_in_group(monkeypatch):
    scheduled = {}

    def fake_schedule_delete(bot, chat_id, message_id, delay):
        scheduled["called"] = (chat_id, message_id, delay)

    monkeypatch.setattr(ephemeral, "schedule_delete", fake_schedule_delete)

    trigger = _trigger_message("supergroup")
    sent = _sent_message("supergroup")

    ephemeral.make_ephemeral(trigger, sent, ttl=30)

    assert scheduled["called"] == (sent.chat.id, sent.message_id, 30)


@pytest.mark.asyncio
async def test_make_ephemeral_noop_in_private_chat(monkeypatch):
    called = False

    def fake_schedule_delete(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(ephemeral, "schedule_delete", fake_schedule_delete)

    trigger = _trigger_message("private")
    sent = _sent_message("private")

    ephemeral.make_ephemeral(trigger, sent, ttl=30)

    assert called is False


@pytest.mark.asyncio
async def test_make_ephemeral_handles_missing_chat_attribute():
    """Bare test doubles without a `.chat` attribute must not raise."""
    trigger = SimpleNamespace()
    sent = _sent_message("supergroup")

    # Should not raise even though `trigger` has no `.chat`.
    ephemeral.make_ephemeral(trigger, sent, ttl=30)


@pytest.mark.asyncio
async def test_cleanup_trigger_deletes_in_group():
    trigger = _trigger_message("supergroup")
    await ephemeral.cleanup_trigger(trigger)
    trigger.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_trigger_leaves_private_chat_alone():
    trigger = _trigger_message("private")
    await ephemeral.cleanup_trigger(trigger)
    trigger.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_delete_calls_bot_delete_message_after_delay():
    bot = SimpleNamespace(delete_message=AsyncMock())
    ephemeral.schedule_delete(bot, chat_id=-100, message_id=7, delay=0)
    # let the fire-and-forget task run
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    bot.delete_message.assert_awaited_once_with(-100, 7)
