"""Observe every group message so commands also satisfy the newcomer rule."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from services.newcomer_guard import mark_newcomer_active


class NewcomerActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user and event.chat.type in ("group", "supergroup"):
            await mark_newcomer_active(event.chat.id, event.from_user.id)
        return await handler(event, data)
