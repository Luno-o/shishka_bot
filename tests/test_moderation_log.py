"""Rule reports for automatic moderation actions (logs chat)."""
import asyncio
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessage
from aiogram.types import (
    Chat,
    Contact,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PhotoSize,
    User,
    VideoNote,
)

from config import config
from handlers import group_events
from services import audit_log
from services.cache import MemberData
from services.moderation_log import describe_rule, log_auto_action, log_auto_event
from services.newcomer_guard import schedule_newcomer_check, stop_newcomer_checks

CHAT_ID = -1001000000001
LOGS_ID = -1001000000099
USER_ID = 555


@pytest.fixture(autouse=True)
def logs_chat(monkeypatch):
    monkeypatch.setattr(config.groups, "logs", LOGS_ID)
    audit_log.reset()


def make_bot():
    return AsyncMock()


def make_message(bot, **content):
    return Message(
        message_id=7,
        date=datetime(2026, 1, 1),
        chat=Chat(id=CHAT_ID, type="supergroup", title="Test <chat>"),
        from_user=User(id=USER_ID, is_bot=False, first_name="Вася"),
        **content,
    ).as_(bot)


def make_member(reputation=0, messages=0, violations=0):
    return MemberData(
        id=1,
        user_id=USER_ID,
        messages_count=messages,
        reputation_points=reputation,
        violations_count_profanity=0,
        violations_count_spam=violations,
        halloween_sweets=0,
        halloween_golden_tickets=0,
    )


def sent_text(bot) -> str:
    return bot.send_message.await_args.args[1]


def was_deleted(bot) -> bool:
    return any(isinstance(call.args[0], DeleteMessage) for call in bot.await_args_list)


# ---------------------------------------------------------------- describe_rule


@pytest.mark.parametrize(
    ("key", "config_key"),
    [
        ("link", "links_rep_threshold"),
        ("invisible_spacing", "links_rep_threshold"),
        ("single_emoji", "single_emoji_rep_threshold"),
        ("location", "links_rep_threshold"),
        ("external_reply", "external_reply_rep_threshold"),
        ("forward", "allow_forwards_threshold"),
        ("media", "allow_media_threshold"),
        ("first_comment", "allow_comments_rep_threshold"),
    ],
    ids=lambda v: str(v),
)
def test_rule_text_names_config_key_and_current_value(monkeypatch, key, config_key):
    monkeypatch.setattr(config.spam, config_key, 4321)

    text = describe_rule(key)

    assert f"spam.{config_key}" in text
    assert "4321" in text


def test_rule_text_follows_config_changes_at_call_time(monkeypatch):
    monkeypatch.setattr(config.spam, "links_rep_threshold", 11)
    first = describe_rule("link")
    monkeypatch.setattr(config.spam, "links_rep_threshold", 99)
    second = describe_rule("link")

    assert "11" in first and "99" not in first
    assert "99" in second


def test_autoban_rule_text_contains_counts_and_thresholds(monkeypatch):
    monkeypatch.setattr(config.spam, "autoban_threshold", 7)
    monkeypatch.setattr(config.spam, "autoban_rep_threshold", 88)

    text = describe_rule("autoban", violations=9)

    assert "9" in text
    assert "spam.autoban_threshold" in text and "7" in text
    assert "spam.autoban_rep_threshold" in text and "88" in text


def test_unknown_rule_key_raises():
    with pytest.raises(KeyError):
        describe_rule("no-such-rule")


# --------------------------------------------------------------- log_auto_action


@pytest.mark.asyncio
async def test_log_contains_rule_author_reputation_and_label(monkeypatch):
    # Why: config.toml overrides the default, so pin the value the test asserts on.
    monkeypatch.setattr(config.spam, "links_rep_threshold", 50)
    bot = make_bot()
    message = make_message(bot, text="hello")

    await log_auto_action(
        message, rule="link", label="🔗 Антиспам (ссылка)", text="hello", reputation=12
    )

    body = sent_text(bot)
    assert bot.send_message.await_args.args[0] == LOGS_ID
    assert "<i>Правило:</i>" in body
    assert "spam.links_rep_threshold" in body
    assert "&lt; 50" in body  # '<' in the rule itself must be escaped for HTML
    assert "<i>Автор:</i>" in body and "Вася" in body
    assert "<i>Репутация:</i> 12" in body
    # Why: generate_log_message upper-cases the label.
    assert "🔗 АНТИСПАМ (ССЫЛКА)" in body


@pytest.mark.asyncio
async def test_log_omits_reputation_when_unknown():
    bot = make_bot()
    message = make_message(bot, text="hello")

    await log_auto_action(message, rule="link", label="L", text="hello")

    assert "Репутация" not in sent_text(bot)


@pytest.mark.asyncio
async def test_log_escapes_html_in_user_text():
    bot = make_bot()
    message = make_message(bot, text="x")

    await log_auto_action(message, rule="link", label="L", text="<script>alert(1)</script> <b>hi")

    body = sent_text(bot)
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
    assert "<b>hi" not in body


@pytest.mark.asyncio
async def test_log_preserves_cyrillic_and_emoji():
    bot = make_bot()
    message = make_message(bot, text="x")

    await log_auto_action(message, rule="link", label="L", text="Привет 🎉 мир")

    assert "Привет 🎉 мир" in sent_text(bot)


@pytest.mark.asyncio
async def test_log_truncates_very_long_text_below_telegram_limit():
    bot = make_bot()
    message = make_message(bot, text="x")

    await log_auto_action(message, rule="link", label="L", text="я" * 10000)

    assert len(sent_text(bot)) < 4096


@pytest.mark.asyncio
@pytest.mark.parametrize("empty", [None, ""], ids=["none", "empty"])
async def test_log_uses_placeholder_for_missing_text(empty):
    bot = make_bot()
    message = make_message(bot, text="x")

    await log_auto_action(message, rule="media", label="L", text=empty)

    assert "[медиа без текста]" in sent_text(bot)


@pytest.mark.asyncio
async def test_log_includes_extra_block():
    bot = make_bot()
    message = make_message(bot, text="x")

    await log_auto_action(message, rule="link", label="L", text="t", extra="<i>Scores:</i> N: 1")

    assert "<i>Scores:</i> N: 1" in sent_text(bot)


@pytest.mark.asyncio
async def test_log_passes_reply_markup_through():
    bot = make_bot()
    message = make_message(bot, text="x")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="ok", callback_data="x")]])

    await log_auto_action(message, rule="link", label="L", text="t", reply_markup=keyboard)

    assert bot.send_message.await_args.kwargs["reply_markup"] is keyboard


@pytest.mark.asyncio
async def test_log_failure_is_swallowed_and_warned(caplog):
    bot = make_bot()
    bot.send_message.side_effect = TelegramBadRequest(method=MagicMock(), message="can't parse")
    message = make_message(bot, text="x")

    with caplog.at_level(logging.WARNING):
        await log_auto_action(message, rule="link", label="L", text="t")

    assert any(record.levelno == logging.WARNING for record in caplog.records)


@pytest.mark.asyncio
async def test_log_not_sent_when_logs_chat_not_configured(monkeypatch, caplog):
    monkeypatch.setattr(config.groups, "logs", 0)
    bot = make_bot()
    message = make_message(bot, text="x")

    with caplog.at_level(logging.WARNING):
        await log_auto_action(message, rule="link", label="L", text="t")

    bot.send_message.assert_not_awaited()
    assert any(record.levelno == logging.WARNING for record in caplog.records)


@pytest.mark.asyncio
async def test_deleted_action_records_audit_entry_with_short_reason():
    bot = make_bot()
    message = make_message(bot, text="x")

    await log_auto_action(message, rule="link", label="L", text="spam text")

    entries = audit_log.get_recent(CHAT_ID)
    assert len(entries) == 1
    assert entries[0].reason == "ссылка"
    assert entries[0].user_id == USER_ID
    assert entries[0].snippet == "spam text"


@pytest.mark.asyncio
async def test_not_deleted_action_records_no_audit_entry():
    bot = make_bot()
    message = make_message(bot, text="x")

    await log_auto_action(message, rule="autoban", label="L", deleted=False)

    assert audit_log.get_recent(CHAT_ID) == []
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_audit_entry_recorded_even_when_log_send_fails():
    bot = make_bot()
    bot.send_message.side_effect = TelegramBadRequest(method=MagicMock(), message="boom")
    message = make_message(bot, text="x")

    await log_auto_action(message, rule="link", label="L", text="t")

    assert len(audit_log.get_recent(CHAT_ID)) == 1


@pytest.mark.asyncio
async def test_log_auto_event_sends_label_and_body_without_message():
    bot = make_bot()

    await log_auto_event(bot, label="🛡️ X", body="тело", chat_title="Чат")

    bot.send_message.assert_awaited_once()
    assert "тело" in sent_text(bot)
    assert "Чат" in sent_text(bot)


# ---------------------------------------------------------------- handler level


@pytest.fixture
def moderation(monkeypatch):
    """Patch member lookups so handlers can run without Telegram or a cache."""
    state = {"member": make_member(reputation=5)}
    monkeypatch.setattr(
        group_events, "retrieve_or_create_member", AsyncMock(side_effect=lambda _id: state["member"])
    )
    monkeypatch.setattr(
        group_events, "retrieve_tgmember", AsyncMock(return_value=MagicMock(status="member"))
    )
    queue = AsyncMock()
    monkeypatch.setattr(group_events, "queue_member_update", queue)
    state["queue"] = queue
    return state


@pytest.mark.asyncio
async def test_ml_spam_deletion_is_logged_with_rule(moderation, monkeypatch):
    monkeypatch.setattr(group_events, "ruspam_predict", AsyncMock(return_value=True))
    bot = make_bot()
    message = make_message(bot, text="Заработок без вложений!!!")

    await group_events.on_user_message(message)

    assert was_deleted(bot)
    body = sent_text(bot)
    assert "<i>Правило:</i>" in body
    assert "ML" in body
    assert "spam.member_messages_threshold" in body
    assert "Заработок без вложений!!!" in body


@pytest.mark.asyncio
async def test_ml_spam_still_penalises_member_when_log_send_fails(moderation, monkeypatch):
    monkeypatch.setattr(group_events, "ruspam_predict", AsyncMock(return_value=True))
    bot = make_bot()
    bot.send_message.side_effect = TelegramBadRequest(method=MagicMock(), message="boom")
    message = make_message(bot, text="spam")

    await group_events.on_user_message(message)

    assert was_deleted(bot)
    moderation["queue"].assert_awaited_once()


@pytest.mark.asyncio
async def test_link_deletion_log_contains_threshold_rule(moderation, monkeypatch):
    monkeypatch.setattr(config.spam, "links_rep_threshold", 77)
    moderation["member"] = make_member(reputation=5)
    bot = make_bot()
    message = make_message(
        bot,
        text="see https://evil.example",
        entities=[{"type": "url", "offset": 4, "length": 20}],
    )

    await group_events.on_user_message(message)

    body = sent_text(bot)
    assert "spam.links_rep_threshold" in body and "77" in body


@pytest.mark.asyncio
async def test_media_in_message_handler_is_logged_with_rule(moderation):
    bot = make_bot()
    message = make_message(
        bot, photo=[PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)]
    )

    await group_events.on_user_message(message)

    assert was_deleted(bot)
    body = sent_text(bot)
    assert "spam.allow_media_threshold" in body
    assert "[медиа без текста]" in body


@pytest.mark.asyncio
async def test_on_user_media_deletion_is_logged_with_rule(moderation):
    bot = make_bot()
    message = make_message(bot, video_note=VideoNote(file_id="f", file_unique_id="u", length=1, duration=1))

    await group_events.on_user_media(message)

    assert was_deleted(bot)
    assert "spam.allow_media_threshold" in sent_text(bot)


@pytest.mark.asyncio
async def test_on_user_media_keeps_message_of_trusted_member_and_sends_no_log(moderation):
    moderation["member"] = make_member(reputation=500)
    bot = make_bot()
    message = make_message(bot, video_note=VideoNote(file_id="f", file_unique_id="u", length=1, duration=1))

    await group_events.on_user_media(message)

    assert not was_deleted(bot)
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_contact_deletion_is_logged_with_rule(moderation):
    bot = make_bot()
    message = make_message(bot, contact=Contact(phone_number="+1", first_name="X"))

    await group_events.on_user_contact(message)

    assert was_deleted(bot)
    assert "<i>Правило:</i>" in sent_text(bot)


@pytest.mark.asyncio
async def test_autoban_log_names_rule_and_does_not_add_audit_entry(moderation, monkeypatch):
    monkeypatch.setattr(config.spam, "autoban_enabled", True)
    monkeypatch.setattr(config.spam, "autoban_threshold", 3)
    monkeypatch.setattr(config.spam, "autoban_rep_threshold", 100)
    member = make_member(reputation=-50, violations=5)
    bot = make_bot()
    message = make_message(bot, text="x")

    await group_events._maybe_autoban(message, member, 10, "ссылка")

    bot.ban_chat_member.assert_awaited_once_with(chat_id=CHAT_ID, user_id=USER_ID)
    body = sent_text(bot)
    assert "spam.autoban_threshold" in body and "spam.autoban_rep_threshold" in body
    assert audit_log.get_recent(CHAT_ID) == []


@pytest.mark.asyncio
async def test_nsfw_report_keeps_keyboard_and_names_rule(moderation):
    bot = make_bot()
    message = make_message(bot, photo=[PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)])

    await group_events._report_nsfw(message, None, moderation["member"], "🔞 NSFW (фото)", "<i>Scores:</i> N: 1")

    assert was_deleted(bot)
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == f"nsfw_ban_{USER_ID}_{CHAT_ID}"
    assert "<i>Правило:</i>" in sent_text(bot)
    assert "nsfw" in sent_text(bot).lower()


# --------------------------------------------------------------- newcomer guard


@pytest.mark.asyncio
async def test_inactive_newcomer_removal_is_reported_with_timeout_rule():
    bot = AsyncMock()
    bot.get_chat_member.return_value = MagicMock(status="member")

    await schedule_newcomer_check(bot, CHAT_ID, 4242, 0.01)
    await asyncio.sleep(0.1)
    await stop_newcomer_checks()

    bot.ban_chat_member.assert_awaited_once()
    body = bot.send_message.await_args.args[1]
    assert bot.send_message.await_args.args[0] == LOGS_ID
    assert "<i>Правило:</i>" in body
    assert "groups.newcomer_message_timeout" in body
    assert "4242" in body


# ------------------------------------------------------- review fix round 1


@pytest.mark.parametrize(
    ("first_name", "must_not_contain", "must_contain"),
    [
        ("<b", "<b ", "&lt;b"),
        ("A&B <i>", "<i>", "A&amp;B &lt;i&gt;"),
        ("Вася 🎉", "&lt;", "Вася 🎉"),
    ],
    ids=["open-tag", "ampersand-and-tag", "cyrillic-emoji"],
)
def test_user_mention_escapes_full_name(first_name, must_not_contain, must_contain):
    from utils.helpers import user_mention

    user = User(id=1, is_bot=False, first_name=first_name)

    text = user_mention(user)

    assert must_contain in text
    assert must_not_contain not in text


@pytest.mark.asyncio
async def test_nsfw_report_is_still_sent_when_delete_fails(moderation, caplog):
    bot = make_bot()

    async def fail_on_delete(method, *args, **kwargs):
        if isinstance(method, DeleteMessage):
            raise TelegramBadRequest(method=method, message="message to delete not found")

    bot.side_effect = fail_on_delete
    message = make_message(bot, photo=[PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)])

    with caplog.at_level(logging.WARNING):
        await group_events._report_nsfw(message, None, moderation["member"], "🔞 NSFW (фото)")

    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.kwargs["reply_markup"] is not None
    assert any(record.levelno == logging.WARNING for record in caplog.records)
