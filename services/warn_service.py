"""
Formal warning ladder.

Unlike the automatic reputation-penalty system used elsewhere in the bot,
!warn is an explicit, visible admin action: each warning is recorded, and
crossing a configured count automatically escalates to a mute (1h, then
1d) and finally a ban. This gives both admins and the warned user a clear,
auditable "warn 2 of 4" trail instead of an opaque reputation number.
"""
from typing import Literal, Optional

from ormar.exceptions import NoMatch

from config import config
from db.models import Warning

Consequence = Optional[Literal["mute_1h", "mute_1d", "ban"]]


def consequence_for(warning_count: int) -> Consequence:
    """
    Pure decision function: given a user's total warning count in a chat,
    return which consequence (if any) should be applied right now.

    Uses the *highest* threshold reached so a jump (e.g. an admin issuing
    several warnings in a row before the bot reacts) still bans rather than
    under-reacting.
    """
    cfg = config.warn
    if not cfg.enabled:
        return None
    if warning_count >= cfg.ban_at:
        return "ban"
    if warning_count >= cfg.mute_1d_at:
        return "mute_1d"
    if warning_count >= cfg.mute_1h_at:
        return "mute_1h"
    return None


async def add_warning(chat_id: int, user_id: int, admin_id: int, reason: str | None) -> int:
    """Record a new warning and return the user's new total count in this chat."""
    await Warning.objects.create(chat_id=chat_id, user_id=user_id, admin_id=admin_id, reason=reason)
    return await count_warnings(chat_id, user_id)


async def count_warnings(chat_id: int, user_id: int) -> int:
    """Total warning count for a user in a specific chat."""
    return await Warning.objects.filter(chat_id=chat_id, user_id=user_id).count()


async def remove_latest_warning(chat_id: int, user_id: int) -> bool:
    """Remove the most recent warning for a user in a chat. Returns True if one was removed."""
    try:
        latest = await Warning.objects.filter(chat_id=chat_id, user_id=user_id).order_by("-date").first()
    except NoMatch:
        return False
    await latest.delete()
    return True


async def clear_warnings(chat_id: int, user_id: int) -> int:
    """Remove all warnings for a user in a chat. Returns how many were removed."""
    count = await count_warnings(chat_id, user_id)
    if count:
        await Warning.objects.filter(chat_id=chat_id, user_id=user_id).delete()
    return count
