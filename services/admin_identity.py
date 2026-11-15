"""Who counts as an admin when a message is written as a chat or channel.

Telegram delivers "anonymous admin" and "send as channel" messages with
``from_user`` set to a shared service bot (GroupAnonymousBot / Channel_Bot)
and the real identity in ``sender_chat``.
"""
from aiogram.types import Message

from config import config
from utils.enums import MemberStatus


def sender_chat_admin_verdict(message: Message) -> bool | None:
    """Decide admin rights for messages written as a chat or channel.

    Pure and synchronous: no API calls.

    Returns:
        None if the message has no ``sender_chat`` (judge the user instead);
        True for the chat itself (anonymous admin) or a linked channel;
        False for automatic forwards and any other channel.
    """
    sender_chat = message.sender_chat
    if sender_chat is None:
        return None
    if message.is_automatic_forward:
        return False
    # Why: anyone can post as their own channel, so only the chat itself and
    # channels explicitly listed in config count. from_user is never consulted
    # here: it is a shared service bot, identical for every such sender.
    return sender_chat.id == message.chat.id or config.groups.is_linked_channel(sender_chat.id)


async def is_admin_sender(message: Message) -> bool:
    """Return True if the author of ``message`` may use admin features."""
    if message.from_user is None:
        return False
    if message.from_user.id == config.bot.owner:
        return True
    verdict = sender_chat_admin_verdict(message)
    if verdict is not None:
        return verdict
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in MemberStatus.admin_statuses()


def actor_id(message: Message) -> int:
    """Return the id to record as the acting admin (chat id for chat/channel senders)."""
    if message.sender_chat is not None:
        return message.sender_chat.id
    return message.from_user.id
