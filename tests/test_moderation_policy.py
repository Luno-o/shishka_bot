from types import SimpleNamespace

import pytest

from config import config
from services.cache import MemberData, flush_member_updates, members_cache, queue_member_update
from services.moderation_policy import is_allowlisted_link_only, is_moderation_exempt


def member_with_reputation(value: int, messages_count: int = 10) -> MemberData:
    return MemberData(
        id=1,
        user_id=1,
        messages_count=messages_count,
        reputation_points=value,
        violations_count_profanity=0,
        violations_count_spam=0,
        halloween_sweets=0,
        halloween_golden_tickets=0,
    )


def test_reputation_boundary():
    assert not is_moderation_exempt(member_with_reputation(9))
    assert not is_moderation_exempt(member_with_reputation(10))
    assert is_moderation_exempt(member_with_reputation(11))


def test_active_member_is_exempt_despite_low_reputation():
    """A member with many good messages is exempt even if reputation dipped
    (e.g. from a single media/voice penalty) - fixes false positives against
    already-active members."""
    trusted_messages = config.cache.trusted_user_messages
    member = member_with_reputation(0, messages_count=trusted_messages)
    assert is_moderation_exempt(member)

    newer_member = member_with_reputation(0, messages_count=trusted_messages - 1)
    assert not is_moderation_exempt(newer_member)


def _url_entity(offset: int, length: int):
    return SimpleNamespace(type="url", offset=offset, length=length, url=None)


def _text_link_entity(offset: int, length: int, url: str):
    return SimpleNamespace(type="text_link", offset=offset, length=length, url=url)


def _message(text: str, entities: list):
    return SimpleNamespace(text=text, caption=None, entities=entities, caption_entities=None)


def test_youtube_link_is_allowlisted():
    text = "check this out https://www.youtube.com/watch?v=abc123"
    url = "https://www.youtube.com/watch?v=abc123"
    message = _message(text, [_url_entity(text.index(url), len(url))])
    assert is_allowlisted_link_only(message, config.spam.link_domain_allowlist)


def test_non_allowlisted_link_is_not_allowlisted():
    text = "join now https://t.me/joinchat/xxxxx"
    url = "https://t.me/joinchat/xxxxx"
    message = _message(text, [_url_entity(text.index(url), len(url))])
    assert not is_allowlisted_link_only(message, config.spam.link_domain_allowlist)


def test_disguised_text_link_cannot_spoof_the_allowlist():
    """The clickable text says 'youtube.com' but the real href doesn't -
    must NOT be allowlisted."""
    message = _message(
        "click youtube.com now",
        [_text_link_entity(6, 11, "https://evil-phish.example/steal")],
    )
    assert not is_allowlisted_link_only(message, ["youtube.com"])


def test_mixed_links_are_not_allowlisted():
    """One safe link plus one unsafe link must still be treated as unsafe."""
    text = "https://youtu.be/abc and https://t.me/spam"
    safe = "https://youtu.be/abc"
    unsafe = "https://t.me/spam"
    message = _message(
        text,
        [
            _url_entity(text.index(safe), len(safe)),
            _url_entity(text.index(unsafe), len(unsafe)),
        ],
    )
    assert not is_allowlisted_link_only(message, ["youtube.com", "youtu.be"])


def test_lookalike_domain_does_not_match():
    text = "https://notyoutube.com/watch?v=1"
    message = _message(text, [_url_entity(0, len(text))])
    assert not is_allowlisted_link_only(message, ["youtube.com"])


@pytest.mark.asyncio
async def test_queued_update_changes_moderation_decision_immediately():
    member = member_with_reputation(10)
    members_cache[member.user_id] = member

    await queue_member_update(member.user_id, reputation_points=1)

    assert is_moderation_exempt(member)
    members_cache.pop(member.user_id, None)
    await flush_member_updates()
