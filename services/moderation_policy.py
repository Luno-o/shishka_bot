"""Central moderation policy and inexpensive content checks."""

from urllib.parse import urlparse

from aiogram.types import Message

from config import config
from services.cache import MemberData, is_trusted_user


def is_moderation_exempt(member: MemberData) -> bool:
    """Users are exempt once they've earned trust either by reputation or by
    sheer message volume.

    The message-count fallback (`is_trusted_user`) matters in practice: a
    long-standing, obviously-human member can still have reputation dip
    below the threshold from a single media/voice-message penalty or a
    false positive, and without this they'd suddenly start getting treated
    like a brand-new account - which is exactly the "active users getting
    blocked" complaint this exists to fix.
    """
    return (
        member.reputation_points > config.spam.exempt_reputation_threshold
        or is_trusted_user(member)
    )


def contains_link(message: Message) -> bool:
    entities = message.entities or message.caption_entities or []
    return any(entity.type in ("url", "text_link") for entity in entities)


def _iter_link_targets(message: Message) -> list[str]:
    """Return the *actual* destination of every link-like entity.

    For a hyperlinked text entity ("text_link") this is `entity.url` - the
    real href - never the clickable text, so a message that displays
    "youtube.com" but actually links elsewhere can't spoof the allowlist.
    For a plain autodetected "url" entity, the visible text *is* the link.
    """
    text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []
    targets = []
    for entity in entities:
        if entity.type == "text_link" and entity.url:
            targets.append(entity.url)
        elif entity.type == "url":
            targets.append(text[entity.offset : entity.offset + entity.length])
    return targets


def _extract_domain(url: str) -> str:
    candidate = url if "://" in url else f"//{url}"
    try:
        return (urlparse(candidate).hostname or "").lower()
    except ValueError:
        return ""


def is_allowlisted_link_only(message: Message, allowlist: list[str]) -> bool:
    """True when *every* link in the message resolves to an allowlisted domain.

    Callers should only consult this after `contains_link()` is already
    True; a message with no links is not considered "allowlisted" here.
    """
    targets = _iter_link_targets(message)
    if not targets:
        return False

    normalized_allowlist = {domain.lower().lstrip(".") for domain in allowlist if domain}
    if not normalized_allowlist:
        return False

    for target in targets:
        domain = _extract_domain(target)
        if not domain:
            return False
        if not any(
            domain == allowed or domain.endswith(f".{allowed}")
            for allowed in normalized_allowlist
        ):
            return False
    return True


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
