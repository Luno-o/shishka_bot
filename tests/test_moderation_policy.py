import pytest

from services.cache import MemberData, flush_member_updates, members_cache, queue_member_update
from services.moderation_policy import is_moderation_exempt


def member_with_reputation(value: int) -> MemberData:
    return MemberData(
        id=1,
        user_id=1,
        messages_count=10,
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


@pytest.mark.asyncio
async def test_queued_update_changes_moderation_decision_immediately():
    member = member_with_reputation(10)
    members_cache[member.user_id] = member

    await queue_member_update(member.user_id, reputation_points=1)

    assert is_moderation_exempt(member)
    members_cache.pop(member.user_id, None)
    await flush_member_updates()
