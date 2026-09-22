import time
from collections import deque

import pytest

from services import raid_guard


@pytest.fixture(autouse=True)
def _clear_raid_state():
    """Raid state is module-level, not per-test - reset it around every test."""
    raid_guard._join_times.clear()
    raid_guard._raid_until.clear()
    raid_guard._raid_alerted.clear()
    yield
    raid_guard._join_times.clear()
    raid_guard._raid_until.clear()
    raid_guard._raid_alerted.clear()


def test_no_raid_below_threshold():
    chat_id = -1001
    threshold = raid_guard.config.raid_guard.join_threshold
    for _ in range(threshold - 1):
        assert raid_guard.record_join(chat_id) is False
    assert raid_guard.is_raid_active(chat_id) is False


def test_raid_detected_at_threshold():
    chat_id = -1002
    threshold = raid_guard.config.raid_guard.join_threshold
    result = False
    for _ in range(threshold):
        result = raid_guard.record_join(chat_id)
    assert result is True
    assert raid_guard.is_raid_active(chat_id) is True


def test_alert_fires_once_per_raid():
    chat_id = -1003
    for _ in range(raid_guard.config.raid_guard.join_threshold):
        raid_guard.record_join(chat_id)

    assert raid_guard.should_send_alert(chat_id) is True
    assert raid_guard.should_send_alert(chat_id) is False
    assert raid_guard.should_send_alert(chat_id) is False


def test_stale_joins_outside_window_are_pruned():
    chat_id = -1004
    old_timestamp = time.time() - (raid_guard.config.raid_guard.window_seconds + 100)
    raid_guard._join_times[chat_id] = deque([old_timestamp] * 10)

    # a single fresh join shouldn't trigger a raid once the old ones expire
    assert raid_guard.record_join(chat_id) is False


def test_clear_raid_resets_everything():
    chat_id = -1005
    for _ in range(raid_guard.config.raid_guard.join_threshold):
        raid_guard.record_join(chat_id)
    assert raid_guard.is_raid_active(chat_id) is True

    raid_guard.clear_raid(chat_id)

    assert raid_guard.is_raid_active(chat_id) is False
    # a fresh raid can be detected again right after a manual clear
    for _ in range(raid_guard.config.raid_guard.join_threshold):
        result = raid_guard.record_join(chat_id)
    assert result is True
    assert raid_guard.should_send_alert(chat_id) is True


def test_disabled_guard_never_flags_a_raid(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        raid_guard.config, "raid_guard",
        SimpleNamespace(enabled=False, join_threshold=1, window_seconds=30, restrict_seconds=60),
    )
    chat_id = -1006
    for _ in range(10):
        assert raid_guard.record_join(chat_id) is False
