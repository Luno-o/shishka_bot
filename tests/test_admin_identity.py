"""Admin recognition for messages written as a chat / linked channel."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiogram.types import CallbackQuery, Chat, Message, User

from config import config
from filters.is_admin import IsAdminFilter
from services.admin_identity import actor_id, is_admin_sender, sender_chat_admin_verdict

CHAT_ID = -1001000000001
LINKED_CHANNEL_ID = -1001000000002
FOREIGN_CHANNEL_ID = -1001000000003
USER_ID = 555
GROUP_ANONYMOUS_BOT_ID = 1087968824
CHANNEL_BOT_ID = 136817688


@pytest.fixture(autouse=True)
def linked_channels():
    original = list(config.groups.linked_channels)
    config.groups.linked_channels = [LINKED_CHANNEL_ID]
    config.groups.rebuild_sets()
    yield
    config.groups.linked_channels = original
    config.groups.rebuild_sets()


@pytest.fixture
def bot():
    mock = MagicMock()
    mock.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
    return mock


def make_message(bot, *, from_user_id=USER_ID, sender_chat_id=None, automatic=False, no_user=False):
    return Message(
        message_id=1,
        date=datetime(2026, 1, 1),
        chat=Chat(id=CHAT_ID, type="supergroup"),
        from_user=None if no_user else User(id=from_user_id, is_bot=False, first_name="U"),
        sender_chat=None if sender_chat_id is None else Chat(id=sender_chat_id, type="channel"),
        is_automatic_forward=automatic or None,
    ).as_(bot)


def anonymous_admin(bot):
    return make_message(bot, from_user_id=GROUP_ANONYMOUS_BOT_ID, sender_chat_id=CHAT_ID)


def linked_channel(bot, automatic=False):
    return make_message(
        bot, from_user_id=CHANNEL_BOT_ID, sender_chat_id=LINKED_CHANNEL_ID, automatic=automatic
    )


def foreign_channel(bot):
    return make_message(bot, from_user_id=CHANNEL_BOT_ID, sender_chat_id=FOREIGN_CHANNEL_ID)


class TestSenderChatVerdict:
    def test_plain_user_message_has_no_verdict(self, bot):
        assert sender_chat_admin_verdict(make_message(bot)) is None

    def test_anonymous_group_admin_is_admin(self, bot):
        assert sender_chat_admin_verdict(anonymous_admin(bot)) is True

    def test_linked_channel_is_admin(self, bot):
        assert sender_chat_admin_verdict(linked_channel(bot)) is True

    def test_foreign_channel_is_not_admin(self, bot):
        assert sender_chat_admin_verdict(foreign_channel(bot)) is False

    def test_automatic_forward_from_linked_channel_is_not_admin(self, bot):
        assert sender_chat_admin_verdict(linked_channel(bot, automatic=True)) is False


class TestIsAdminSender:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "build",
        [anonymous_admin, linked_channel],
        ids=["anonymous-group-admin", "linked-channel"],
    )
    async def test_accepts_without_api_call(self, bot, build):
        assert await is_admin_sender(build(bot)) is True
        bot.get_chat_member.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_foreign_channel_without_api_call(self, bot):
        assert await is_admin_sender(foreign_channel(bot)) is False
        bot.get_chat_member.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_automatic_forward_from_linked_channel(self, bot):
        assert await is_admin_sender(linked_channel(bot, automatic=True)) is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("administrator", True),
            ("creator", True),
            ("member", False),
            ("restricted", False),
            ("left", False),
        ],
    )
    async def test_plain_user_follows_chat_member_status(self, bot, status, expected):
        bot.get_chat_member.return_value = MagicMock(status=status)
        assert await is_admin_sender(make_message(bot)) is expected
        bot.get_chat_member.assert_awaited_once_with(CHAT_ID, USER_ID)

    @pytest.mark.asyncio
    async def test_owner_is_admin_without_api_call(self, bot):
        message = make_message(bot, from_user_id=config.bot.owner)
        assert await is_admin_sender(message) is True
        bot.get_chat_member.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_without_from_user_is_not_admin(self, bot):
        assert await is_admin_sender(make_message(bot, no_user=True)) is False

    @pytest.mark.asyncio
    async def test_service_bot_without_sender_chat_is_not_admin(self, bot):
        # Why: GroupAnonymousBot id alone must never grant admin rights.
        message = make_message(bot, from_user_id=GROUP_ANONYMOUS_BOT_ID)
        assert await is_admin_sender(message) is False


class TestActorId:
    def test_uses_sender_chat_id_when_present(self, bot):
        assert actor_id(anonymous_admin(bot)) == CHAT_ID

    def test_uses_linked_channel_id(self, bot):
        assert actor_id(linked_channel(bot)) == LINKED_CHANNEL_ID

    def test_uses_user_id_for_plain_user(self, bot):
        assert actor_id(make_message(bot)) == USER_ID


class TestIsAdminFilter:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("build", "is_admin", "expected"),
        [
            (anonymous_admin, True, True),
            (linked_channel, True, True),
            (foreign_channel, True, False),
            (anonymous_admin, False, False),
            (foreign_channel, False, True),
        ],
        ids=["anon-admin", "linked", "foreign", "anon-inverted", "foreign-inverted"],
    )
    async def test_message_sender_chat(self, bot, build, is_admin, expected):
        assert await IsAdminFilter(is_admin=is_admin)(build(bot)) is expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "is_admin", "expected"),
        [("administrator", True, True), ("member", True, False), ("member", False, True)],
    )
    async def test_message_plain_user(self, bot, status, is_admin, expected):
        bot.get_chat_member.return_value = MagicMock(status=status)
        assert await IsAdminFilter(is_admin=is_admin)(make_message(bot)) is expected

    @pytest.mark.asyncio
    async def test_message_without_from_user_is_rejected(self, bot):
        assert await IsAdminFilter()(make_message(bot, no_user=True)) is False

    @pytest.mark.asyncio
    async def test_callback_query_uses_clicker_chat_member_status(self, bot):
        bot.get_chat_member.return_value = MagicMock(status="administrator")
        message = make_message(bot)
        call = CallbackQuery(
            id="1",
            from_user=User(id=USER_ID, is_bot=False, first_name="U"),
            chat_instance="x",
            message=message,
        ).as_(bot)
        assert await IsAdminFilter()(call) is True
        bot.get_chat_member.assert_awaited_once_with(CHAT_ID, USER_ID)
