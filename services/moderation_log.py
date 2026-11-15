"""
Reports of automatic moderation actions to the logs chat.

Every automatic deletion / ban / kick the bot performs goes through here so
the admins always see WHICH rule fired and with which configured threshold.

Why rule texts are callables: thresholds live in config and may be changed at
runtime (tests, reloads), so they are formatted when the log is written, not
at import time.
Why sending never raises: a broken logs chat (bad id, removed bot, HTML the
API rejects) must not abort the moderation handler after the message was
already deleted - the remaining penalties and autoban still have to run.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, Message

from config import config
from services.audit_log import record_deletion
from utils.helpers import generate_log_message, user_mention

logger = logging.getLogger(__name__)

# Why: Telegram caps a message at 4096 chars; leave room for label, rule, author.
_TEXT_LIMIT = 1500
_NO_TEXT = "[медиа без текста]"


@dataclass(frozen=True)
class Rule:
    """A moderation rule: short audit label plus a config-aware description."""

    short: str
    describe: Callable[..., str]


def _rep_rule(subject: str, threshold_key: str) -> Callable[..., str]:
    """Build a describer for '<subject> from a member with reputation below X'."""

    def describe() -> str:
        value = getattr(config.spam, threshold_key)
        return f"{subject} от участника с репутацией < {value} (spam.{threshold_key})"

    return describe


def _ml_spam() -> str:
    return (
        "ML-классификатор спама: участник с < "
        f"{config.spam.member_messages_threshold} сообщений (spam.member_messages_threshold) "
        f"или репутацией < {config.spam.member_reputation_threshold} "
        "(spam.member_reputation_threshold)"
    )


def _first_comment() -> str:
    return (
        "первый комментарий под постом канала от участника с репутацией < "
        f"{config.spam.allow_comments_rep_threshold} (spam.allow_comments_rep_threshold) "
        f"в течение {config.spam.remove_first_comments_interval} с после поста "
        "(spam.remove_first_comments_interval)"
    )


def _nsfw(subject: str) -> Callable[..., str]:
    def describe() -> str:
        return (
            f"NSFW-классификатор ({subject}) для участника с репутацией < "
            f"{config.nsfw.check_rep_threshold} (nsfw.check_rep_threshold)"
        )

    return describe


def _autoban(violations: int | None = None) -> str:
    count = f"{violations} нарушений" if violations is not None else "число нарушений"
    return (
        f"{count} ≥ {config.spam.autoban_threshold} (spam.autoban_threshold) "
        f"и репутация < {config.spam.autoban_rep_threshold} (spam.autoban_rep_threshold)"
    )


def _newcomer_timeout() -> str:
    return (
        "новичок не написал сообщение за "
        f"{config.groups.newcomer_message_timeout} с (groups.newcomer_message_timeout)"
    )


RULES: dict[str, Rule] = {
    "cn_spam": Rule("CN-спам", lambda: "китайские иероглифы в тексте сообщения"),
    "invisible_spacing": Rule(
        "невидимые символы", _rep_rule("невидимые символы", "links_rep_threshold")
    ),
    "single_emoji": Rule(
        "одинокий эмодзи", _rep_rule("одиночный эмодзи", "single_emoji_rep_threshold")
    ),
    "link": Rule("ссылка", _rep_rule("ссылка", "links_rep_threshold")),
    "ml_spam": Rule("ML-спам", _ml_spam),
    "media": Rule("медиа", _rep_rule("медиа", "allow_media_threshold")),
    "contact": Rule("контакт", lambda: "контакты разрешены только администраторам"),
    "location": Rule("геолокация", _rep_rule("геолокация", "links_rep_threshold")),
    "external_reply": Rule(
        "кросс-чат", _rep_rule("ответ из другого чата", "external_reply_rep_threshold")
    ),
    "forward": Rule("форвард", _rep_rule("пересылка", "allow_forwards_threshold")),
    "first_comment": Rule("первый коммент (антибот)", _first_comment),
    "nsfw_photo": Rule("🔞 NSFW (фото)", _nsfw("фото")),
    "nsfw_profile": Rule("🔞 NSFW (профиль)", _nsfw("фото профиля")),
    "autoban": Rule("автобан", _autoban),
    "newcomer_timeout": Rule("новичок молчит", _newcomer_timeout),
    "unwanted_bot": Rule(
        "бот без прав", lambda: "добавленные боты без прав администратора удаляются"
    ),
    "raid": Rule(
        "рейд",
        lambda: "всплеск новых участников (raid_guard.join_threshold за raid_guard.window_seconds)",
    ),
}


def describe_rule(key: str, **params: int) -> str:
    """Return the human-readable rule text with current config values.

    Args:
        key: A key of `RULES`.
        **params: Dynamic values some rules need (e.g. `violations` for autoban).

    Raises:
        KeyError: If `key` is not a known rule.
    """
    return RULES[key].describe(**params)


def _build_body(
    *,
    text: str | None,
    include_text: bool,
    extra: str | None,
    rule_text: str,
    author: str,
    reputation: int | None,
) -> str:
    """Assemble the HTML body; all user-provided text is escaped here."""
    parts: list[str] = []
    if include_text:
        parts.append(escape((text or _NO_TEXT)[:_TEXT_LIMIT]))
    elif text:
        parts.append(escape(text[:_TEXT_LIMIT]))
    if extra:
        parts.append(extra)
    # Why: rule texts contain "<" (e.g. "репутацией < 50"), invalid in HTML mode.
    parts.append(f"<i>Правило:</i> {escape(rule_text)}")
    parts.append(f"<i>Автор:</i> {author}")
    if reputation is not None:
        parts.append(f"<i>Репутация:</i> {reputation}")
    return "\n\n".join(parts)


async def _send(bot: Bot, text: str, reply_markup: InlineKeyboardMarkup | None) -> None:
    """Send to the logs chat, downgrading every Telegram failure to a warning."""
    if not config.groups.logs:
        logger.warning("Logs chat is not configured; skipping moderation log")
        return
    try:
        await bot.send_message(config.groups.logs, text, reply_markup=reply_markup)
    except TelegramAPIError as err:
        logger.warning("Could not send moderation log: %s", err)


async def log_auto_action(
    message: Message,
    *,
    rule: str,
    label: str,
    text: str | None = None,
    extra: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
    reputation: int | None = None,
    deleted: bool = True,
    rule_params: dict[str, int] | None = None,
) -> None:
    """Report an automatic action on `message` to the logs chat.

    Never raises on Telegram errors or a missing logs chat.

    Args:
        message: The offending message (author and chat are taken from it).
        rule: Key of `RULES`.
        label: Log label, e.g. "🔗 Антиспам (ссылка)".
        text: Message text; user text is HTML-escaped and truncated. For a
            deletion a missing text shows a "no text" placeholder.
        extra: Ready-made HTML block shown after the text (caller escapes).
        reply_markup: Optional keyboard attached to the log.
        reputation: Author reputation to show, if known.
        deleted: True when the message was deleted (adds an audit entry);
            False for actions without deletion such as an autoban.
        rule_params: Dynamic values for the rule text.

    Raises:
        KeyError: If `rule` is not a known rule (programming error).
    """
    if deleted:
        record_deletion(message.chat.id, message.from_user.id, RULES[rule].short, text)
    body = _build_body(
        text=text,
        include_text=deleted,
        extra=extra,
        rule_text=describe_rule(rule, **(rule_params or {})),
        author=user_mention(message.from_user),
        reputation=reputation,
    )
    title = escape(message.chat.title) if message.chat.title else None
    await _send(message.bot, generate_log_message(body, label, title), reply_markup)


async def log_auto_event(
    bot: Bot,
    *,
    label: str,
    body: str,
    chat_title: str | None = None,
) -> None:
    """Report an automatic action that has no triggering message.

    Args:
        bot: Bot used to send the log.
        label: Log label.
        body: Ready-made HTML body; the caller escapes user data.
        chat_title: Title of the affected chat, escaped here.
    """
    title = escape(chat_title) if chat_title else None
    await _send(bot, generate_log_message(body, label, title), None)
