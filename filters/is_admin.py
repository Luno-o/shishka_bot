from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from config import config
from utils.enums import MemberStatus


class IsAdminFilter(BaseFilter):
    """
    Filter that checks if the user is a chat admin.
    Supports anonymous admins (GroupAnonymousBot).
    """

    def __init__(self, is_admin: bool = True) -> None:
        self.is_admin = is_admin

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        if event.from_user is None:
            return False

        # Если это анонимный админ (GroupAnonymousBot)
        if event.from_user.id == 1087968824:  # ID GroupAnonymousBot
            # Для анонимных админов проверяем sender_chat
            if isinstance(event, Message) and event.sender_chat:
                # Это сообщение от анонимного админа - пропускаем
                return True if self.is_admin else False
            # Если это просто бот, но не анонимный админ - не пропускаем
            return False

        # Владелец всегда админ
        if event.from_user.id == config.bot.owner:
            return True if self.is_admin else False

        if isinstance(event, CallbackQuery):
            if event.message is None:
                return False
            chat_id = event.message.chat.id
            bot = event.bot
        else:
            chat_id = event.chat.id
            bot = event.bot

        member = await bot.get_chat_member(chat_id, event.from_user.id)
        user_is_admin = member.status in MemberStatus.admin_statuses()

        if self.is_admin:
            return user_is_admin
        return not user_is_admin