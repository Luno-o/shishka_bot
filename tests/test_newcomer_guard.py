import asyncio

import pytest

from db.models import PendingNewcomer
from services.newcomer_guard import (
    mark_newcomer_active,
    schedule_newcomer_check,
    stop_newcomer_checks,
)


class FakeMember:
    status = "member"


class FakeBot:
    def __init__(self):
        self.banned = []
        self.unbanned = []

    async def get_chat_member(self, chat_id, user_id):
        return FakeMember()

    async def ban_chat_member(self, chat_id, user_id):
        self.banned.append((chat_id, user_id))

    async def unban_chat_member(self, chat_id, user_id, only_if_banned):
        self.unbanned.append((chat_id, user_id, only_if_banned))


@pytest.mark.asyncio
async def test_inactive_newcomer_is_removed():
    bot = FakeBot()
    await schedule_newcomer_check(bot, -100, 10, 0.01)
    await asyncio.sleep(0.05)

    record = await PendingNewcomer.objects.get(chat_id=-100, user_id=10)
    assert record.status == "removed"
    assert bot.banned == [(-100, 10)]
    assert bot.unbanned == [(-100, 10, True)]


@pytest.mark.asyncio
async def test_first_message_cancels_removal():
    bot = FakeBot()
    await schedule_newcomer_check(bot, -100, 11, 0.05)
    assert await mark_newcomer_active(-100, 11)
    await asyncio.sleep(0.08)

    record = await PendingNewcomer.objects.get(chat_id=-100, user_id=11)
    assert record.status == "active"
    assert not bot.banned
    await stop_newcomer_checks()
