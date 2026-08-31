"""Central moderation policy and inexpensive content checks."""

from aiogram.types import Message

from config import config
from services.cache import MemberData


def is_moderation_exempt(member: MemberData) -> bool:
    """Users above the configured reputation threshold bypass moderation."""
    return member.reputation_points > config.spam.exempt_reputation_threshold


def contains_link(message: Message) -> bool:
    entities = message.entities or message.caption_entities or []
    return any(entity.type in ("url", "text_link") for entity in entities)


def is_single_emoji(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 10:
        return False

    skip = {0xFE0F, 0x200D, 0x20E3}
    base_count = 0
    all_regional = True

    for char in stripped:
        codepoint = ord(char)
        if codepoint in skip or 0x1F3FB <= codepoint <= 0x1F3FF:
            continue

        is_emoji = (
            0x1F600 <= codepoint <= 0x1F64F
            or 0x1F300 <= codepoint <= 0x1F5FF
            or 0x1F680 <= codepoint <= 0x1F6FF
            or 0x1F700 <= codepoint <= 0x1FA6F
            or 0x1FA70 <= codepoint <= 0x1FAFF
            or 0x2600 <= codepoint <= 0x27BF
            or 0x1F1E0 <= codepoint <= 0x1F1FF
            or 0x2300 <= codepoint <= 0x23FF
            or 0x2B00 <= codepoint <= 0x2BFF
            or codepoint in (0x00A9, 0x00AE, 0x2122)
        )
        if not is_emoji:
            return False
        if not 0x1F1E0 <= codepoint <= 0x1F1FF:
            all_regional = False
        base_count += 1

    return base_count == 1 or (base_count == 2 and all_regional)


def contains_invisible_spacing(text: str) -> bool:
    invisible_spacing = {0x115F, 0x1160, 0x3164, 0xFFA0}
    return any(ord(char) in invisible_spacing for char in text)


def contains_chinese(text: str) -> bool:
    return any(
        0x4E00 <= ord(char) <= 0x9FFF
        or 0x3400 <= ord(char) <= 0x4DBF
        or 0x20000 <= ord(char) <= 0x2A6DF
        or 0xF900 <= ord(char) <= 0xFAFF
        for char in text
    )
