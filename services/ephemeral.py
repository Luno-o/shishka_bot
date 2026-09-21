"""
Ephemeral message helpers.

Telegram has no native "ephemeral message" concept (unlike some other
platforms), so this module fakes it the standard way: send the reply as
usual, then auto-delete it a little later, and clean up the command that
triggered it so groups don't accumulate a trail of `/rules`, `/help` and
`/me` clutter.

Used by handlers that should not leave a permanent footprint in the group:
rules, help, and the personal stats/reputation command (`!me`).
"""

import asyncio
import logging
from contextlib import suppress
from typing import Optional

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from config import config

logger = logging.getLogger(__name__)

_GROUP_CHAT_TYPES = {"group", "supergroup"}


def _is_group_chat(message) -> bool:
    """True if `message` looks like it belongs to a group/supergroup chat.

    Defensive against test doubles / partial mocks that don't set `.chat`.
    """
    chat = getattr(message, "chat", None)
    chat_type = getattr(chat, "type", None)
    return chat_type in _GROUP_CHAT_TYPES


async def _delete_after(bot, chat_id: int, message_id: int, delay: float) -> None:
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        await bot.delete_message(chat_id, message_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        # Message was already deleted/chat left - nothing to do.
        pass
    except Exception:
        logger.exception("Failed to auto-delete ephemeral message %s in chat %s", message_id, chat_id)


def schedule_delete(bot, chat_id: int, message_id: int, delay: float) -> None:
    """Fire-and-forget: delete a message after `delay` seconds."""
    asyncio.create_task(_delete_after(bot, chat_id, message_id, delay))


async def delete_silently(message: Message) -> None:
    """Best-effort immediate delete (used to clean up trigger commands)."""
    with suppress(TelegramBadRequest, TelegramForbiddenError, Exception):
        await message.delete()


async def cleanup_trigger(message: Message) -> None:
    """Delete the message that triggered an ephemeral command (groups only).

    Private chats are left alone: there's no "clutter" problem in a 1:1
    conversation with the bot, and deleting the user's own message there
    would be surprising rather than helpful.
    """
    if not config.ephemeral.enabled or not config.ephemeral.delete_trigger:
        return
    if not _is_group_chat(message):
        return
    await delete_silently(message)


def make_ephemeral(message: Message, sent: Optional[Message], ttl: int) -> None:
    """Schedule auto-deletion of a bot reply, respecting config and chat type.

    `message` is the triggering update (used only to decide whether we're in
    a group chat); `sent` is the message the bot actually sent, if any.
    """
    if sent is None:
        return
    if not config.ephemeral.enabled:
        return
    if not _is_group_chat(message):
        return
    schedule_delete(sent.bot, sent.chat.id, sent.message_id, ttl)
