from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from config import config
from services.admin_identity import is_admin_sender
from utils.enums import MemberStatus


class IsAdminFilter(BaseFilter):
    """
    Filter that checks if the user is a chat admin.
    Supports anonymous admins and linked channels for messages.
    """

    def __init__(self, is_admin: bool = True) -> None:
        self.is_admin = is_admin

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        if event.from_user is None:
            return False

        if isinstance(event, Message):
            user_is_admin = await is_admin_sender(event)
        elif event.from_user.id == config.bot.owner:
            user_is_admin = True
        elif event.message is None:
            return False
        else:
            member = await event.bot.get_chat_member(event.message.chat.id, event.from_user.id)
            user_is_admin = member.status in MemberStatus.admin_statuses()

        if self.is_admin:
            return user_is_admin
        return not user_is_admin