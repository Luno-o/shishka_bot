"""Remove newcomers who do not send a message within the grace period."""

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import ormar
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from db.models import PendingNewcomer

logger = logging.getLogger(__name__)

_pending: dict[tuple[int, int], asyncio.Task] = {}


def _utc_now() -> datetime:
    """Return naive UTC to match SQLite DateTime round-trips."""
    return datetime.now(UTC).replace(tzinfo=None)


async def schedule_newcomer_check(bot: Bot, chat_id: int, user_id: int, timeout_seconds: int) -> None:
    """Persist and start an inactivity check for a newcomer."""
    key = (chat_id, user_id)
    cancel_newcomer_check(chat_id, user_id)

    try:
        existing = await PendingNewcomer.objects.get(chat_id=chat_id, user_id=user_id)
    except ormar.NoMatch:
        existing = None
    deadline = _utc_now() + timedelta(seconds=timeout_seconds)
    if existing:
        existing.deadline_at = deadline
        existing.status = "pending"
        await existing.update()
        record_id = existing.id
    else:
        record = await PendingNewcomer.objects.create(
            chat_id=chat_id,
            user_id=user_id,
            deadline_at=deadline,
            status="pending",
        )
        record_id = record.id

    task = asyncio.create_task(_remove_if_inactive(bot, record_id, chat_id, user_id, timeout_seconds))
    _pending[key] = task
    task.add_done_callback(lambda completed, task_key=key: _discard_task(task_key, completed))


async def mark_newcomer_active(chat_id: int, user_id: int) -> bool:
    """Cancel a pending check after the user's first message."""
    cancelled = cancel_newcomer_check(chat_id, user_id)
    if not cancelled:
        return False
    updated = await PendingNewcomer.objects.filter(
        chat_id=chat_id,
        user_id=user_id,
    ).update(status="active")
    return cancelled or bool(updated)


async def start_newcomer_checks(bot: Bot) -> None:
    """Restore pending checks after a restart."""
    records = await PendingNewcomer.objects.filter(status="pending").all()
    now = _utc_now()
    for record in records:
        key = (record.chat_id, record.user_id)
        cancel_newcomer_check(*key)
        delay = max(0.0, (record.deadline_at - now).total_seconds())
        task = asyncio.create_task(
            _remove_if_inactive(bot, record.id, record.chat_id, record.user_id, delay)
        )
        _pending[key] = task
        task.add_done_callback(lambda completed, task_key=key: _discard_task(task_key, completed))


def cancel_newcomer_check(chat_id: int, user_id: int) -> bool:
    task = _pending.pop((chat_id, user_id), None)
    if task is None:
        return False
    if not task.done():
        task.cancel()
    return True


async def stop_newcomer_checks() -> None:
    tasks = list(_pending.values())
    _pending.clear()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def _discard_task(key: tuple[int, int], task: asyncio.Task) -> None:
    if _pending.get(key) is task:
        _pending.pop(key, None)


async def _remove_if_inactive(
    bot: Bot,
    record_id: int,
    chat_id: int,
    user_id: int,
    timeout_seconds: float,
) -> None:
    try:
        await asyncio.sleep(timeout_seconds)

        claimed = await PendingNewcomer.objects.filter(
            id=record_id,
            status="pending",
        ).update(status="removing")
        if not claimed:
            return

        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in ("left", "kicked", "administrator", "creator"):
            await PendingNewcomer.objects.filter(id=record_id).update(status="inactive")
            return

        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        await bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
        await PendingNewcomer.objects.filter(id=record_id).update(status="removed")
        logger.info("Removed inactive newcomer %s from chat %s", user_id, chat_id)
    except asyncio.CancelledError:
        raise
    except (TelegramBadRequest, TelegramForbiddenError):
        await PendingNewcomer.objects.filter(id=record_id).update(status="error")
        logger.warning("Could not remove inactive newcomer %s from chat %s", user_id, chat_id)
    except Exception:
        logger.exception("Unexpected error while checking newcomer %s in chat %s", user_id, chat_id)
    finally:
        with suppress(KeyError):
            current = asyncio.current_task()
            key = (chat_id, user_id)
            if _pending[key] is current:
                del _pending[key]
