"""Filters for natural-language bot requests."""

import re

from aiogram.filters import BaseFilter
from aiogram.types import Message

_HELP_WORDS = r"(?:help|х[еэ]лп|помоги(?:те|ти)?|помощь)"
_BOT_WORDS = r"(?:шиш(?:ка|ке|ку)?|shishka|бот(?:а|у)?)"
_HELP_PATTERNS = (
    re.compile(rf"^(?:{_BOT_WORDS}\s+)?{_HELP_WORDS}(?:\s+{_BOT_WORDS})?[!?.\s]*$", re.IGNORECASE),
    re.compile(rf"^{_BOT_WORDS}[,\s]+{_HELP_WORDS}[!?.\s]*$", re.IGNORECASE),
)

_TAROT_PATTERNS = (
    re.compile(
        rf"^(?:{_BOT_WORDS}[,\s]+)?(?:что|какая|какую)\s+"
        rf"(?:у\s+меня\s+)?(?:сегодня\s+)?(?:шишка|судьба|карта)(?:\s+дня)?[!?.\s]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:моя\s+)?(?:шишка|судьба|карта)\s+(?:на\s+)?сегодня[!?.\s]*$",
        re.IGNORECASE,
    ),
    re.compile(r"^шиш[-\s]?таро[!?.\s]*$", re.IGNORECASE),
)


def is_help_request(text: str | None) -> bool:
    """Return whether text is a supported natural-language help request."""
    if not text:
        return False
    normalized = " ".join(text.strip().split())
    return any(pattern.fullmatch(normalized) for pattern in _HELP_PATTERNS)


def is_tarot_request(text: str | None) -> bool:
    """Return whether text asks Shishka for today's fortune."""
    if not text:
        return False
    normalized = " ".join(text.strip().split())
    return any(pattern.fullmatch(normalized) for pattern in _TAROT_PATTERNS)


class HelpRequestFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return is_help_request(message.text)


class TarotRequestFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return is_tarot_request(message.text)
