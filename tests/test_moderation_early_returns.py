"""Auto-moderation must skip chat / linked-channel senders but not foreign channels."""
import random
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.methods import DeleteMessage
from aiogram.types import (
    Chat,
    Contact,
    Message,
    MessageOriginHiddenUser,
    User,
    VideoNote,
    Voice,
)

from config import config
from handlers import group_events
from services import audit_log
from services.cache import MemberData

CHAT_ID = -1001000000001
LINKED_CHANNEL_ID = -1001000000002
FOREIGN_CHANNEL_ID = -1001000000003
LOGS_ID = -1001000000099
CHANNEL_BOT_ID = 136817688


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setattr(config.groups, "logs", LOGS_ID)
    monkeypatch.setattr(config.spam, "links_rep_threshold", 50)
    original = list(config.groups.linked_channels)
    config.groups.linked_channels = [LINKED_CHANNEL_ID]
    config.groups.rebuild_sets()
    audit_log.reset()
    yield
    config.groups.linked_channels = original
    config.groups.rebuild_sets()


@pytest.fixture
def queue(monkeypatch):
    """Patch member lookups: a brand-new 0-rep member, never an admin."""
    member = MemberData(
        id=1, user_id=CHANNEL_BOT_ID, messages_count=0, reputation_points=0,
        violations_count_profanity=0, violations_count_spam=0,
        halloween_sweets=0, halloween_golden_tickets=0,
    )
    monkeypatch.setattr(group_events, "retrieve_or_create_member", AsyncMock(return_value=member))
    monkeypatch.setattr(
        group_events, "retrieve_tgmember", AsyncMock(return_value=MagicMock(status="member"))
    )
    mock = AsyncMock()
    monkeypatch.setattr(group_events, "queue_member_update", mock)
    return mock


def make_message(bot, sender_chat_id, **content):
    return Message(
        message_id=7,
        date=datetime(2026, 1, 1),
        chat=Chat(id=CHAT_ID, type="supergroup", title="Chat"),
        from_user=User(id=CHANNEL_BOT_ID, is_bot=True, first_name="Channel"),
        sender_chat=Chat(id=sender_chat_id, type="channel"),
        **content,
    ).as_(bot)


def was_deleted(bot) -> bool:
    return any(isinstance(call.args[0], DeleteMessage) for call in bot.await_args_list)


TRUSTED_SENDERS = pytest.mark.parametrize(
    "sender_chat_id", [CHAT_ID, LINKED_CHANNEL_ID], ids=["anonymous-admin", "linked-channel"]
)

LINK_CONTENT = {"text": "see https://evil.example", "entities": [{"type": "url", "offset": 4, "length": 20}]}
VIDEO_NOTE = {"video_note": VideoNote(file_id="f", file_unique_id="u", length=1, duration=1)}
CONTACT = {"contact": Contact(phone_number="+1", first_name="X")}
FORWARD = {"forward_origin": MessageOriginHiddenUser(date=datetime(2026, 1, 1), sender_user_name="Z")}

# (handler name, message content): each deletes a 0-rep stranger and logs it.
DELETING_HANDLERS = pytest.mark.parametrize(
    ("handler", "content"),
    [
        ("on_user_message", LINK_CONTENT),
        ("on_user_media", VIDEO_NOTE),
        ("on_user_contact", CONTACT),
        ("on_user_forward", FORWARD),
    ],
    ids=["link", "media", "contact", "forward"],
)


@pytest.mark.asyncio
@TRUSTED_SENDERS
@DELETING_HANDLERS
async def test_chat_and_linked_channel_senders_are_not_moderated(queue, handler, content, sender_chat_id):
    bot = AsyncMock()
    message = make_message(bot, sender_chat_id, **content)

    await getattr(group_events, handler)(message)

    assert not was_deleted(bot)
    queue.assert_not_awaited()
    bot.send_message.assert_not_awaited()
    assert audit_log.get_recent(CHAT_ID) == []


@pytest.mark.asyncio
@DELETING_HANDLERS
async def test_foreign_channel_sender_is_still_deleted_and_logged(queue, handler, content):
    bot = AsyncMock()
    message = make_message(bot, FOREIGN_CHANNEL_ID, **content)

    await getattr(group_events, handler)(message)

    assert was_deleted(bot)
    bot.send_message.assert_awaited_once()
    assert "<i>Правило:</i>" in bot.send_message.await_args.args[1]


@pytest.mark.asyncio
async def test_automatic_forward_from_linked_channel_is_not_deleted_as_forward(queue):
    bot = AsyncMock()
    message = make_message(bot, LINKED_CHANNEL_ID, is_automatic_forward=True, **FORWARD)

    await group_events.on_user_forward(message)

    assert not was_deleted(bot)
    bot.send_message.assert_not_awaited()


@pytest.fixture
def always_reply(monkeypatch):
    # Why: on_user_voice only reacts with 75% probability; force the reaction.
    monkeypatch.setattr(random, "random", lambda: 0.0)


VOICE = {"voice": Voice(file_id="f", file_unique_id="u", duration=1)}


@pytest.mark.asyncio
@TRUSTED_SENDERS
async def test_voice_from_chat_or_linked_channel_gets_no_reaction_or_penalty(
    queue, always_reply, sender_chat_id
):
    bot = AsyncMock()
    message = make_message(bot, sender_chat_id, **VOICE)

    await group_events.on_user_voice(message)

    queue.assert_not_awaited()
    bot.assert_not_awaited()


@pytest.mark.asyncio
async def test_voice_from_foreign_channel_is_still_penalised(queue, always_reply):
    bot = AsyncMock()
    message = make_message(bot, FOREIGN_CHANNEL_ID, **VOICE)

    await group_events.on_user_voice(message)

    queue.assert_awaited_once()
