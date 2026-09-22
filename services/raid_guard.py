"""
Mass-join raid detection.

Spam/scam raids on Telegram groups typically look like a burst of many
accounts (often freshly created, sometimes bots) joining within a few
seconds of each other. The normal per-user newcomer checks (activity
deadline, reputation exemption, etc.) are too slow to react to this on
their own, so this module tracks join timestamps per chat and flags a
"raid" once too many joins happen too quickly - callers can then react by
temporarily restricting new joiners until an admin can look.
"""
import logging
import time
from collections import deque

from config import config

logger = logging.getLogger(__name__)

# chat_id -> deque of join timestamps (time.time()), trimmed to the window
_join_times: dict[int, deque] = {}

# chat_id -> unix timestamp until which raid mode is active
_raid_until: dict[int, float] = {}

# chat_id -> whether the "raid detected" alert has already been sent for
# the currently-active raid (avoids spamming the log channel on every join)
_raid_alerted: set[int] = set()


def _prune(chat_id: int, now: float) -> None:
    window = config.raid_guard.window_seconds
    times = _join_times.get(chat_id)
    if not times:
        return
    while times and now - times[0] > window:
        times.popleft()


def record_join(chat_id: int) -> bool:
    """
    Record a join event for chat_id.

    Returns True if this join happened while a raid is (now or already)
    considered active, meaning the caller should apply raid-mode handling.
    """
    if not config.raid_guard.enabled:
        return False

    now = time.time()
    times = _join_times.setdefault(chat_id, deque())
    times.append(now)
    _prune(chat_id, now)

    if len(times) >= config.raid_guard.join_threshold:
        _raid_until[chat_id] = now + config.raid_guard.restrict_seconds
        logger.warning(
            "Raid detected in chat %s: %d joins within %ds",
            chat_id, len(times), config.raid_guard.window_seconds,
        )

    return is_raid_active(chat_id)


def is_raid_active(chat_id: int) -> bool:
    """Check whether raid mode is currently active for a chat."""
    until = _raid_until.get(chat_id)
    if until is None:
        return False
    if time.time() >= until:
        _raid_until.pop(chat_id, None)
        _raid_alerted.discard(chat_id)
        return False
    return True


def raid_restrict_seconds() -> int:
    return config.raid_guard.restrict_seconds


def should_send_alert(chat_id: int) -> bool:
    """
    Returns True exactly once per raid: the first time it's checked while
    the raid is active. Subsequent calls (same raid) return False.
    """
    if chat_id in _raid_alerted:
        return False
    _raid_alerted.add(chat_id)
    return True


def clear_raid(chat_id: int) -> None:
    """Manually clear raid state for a chat (e.g. an admin override)."""
    _raid_until.pop(chat_id, None)
    _raid_alerted.discard(chat_id)
    _join_times.pop(chat_id, None)
