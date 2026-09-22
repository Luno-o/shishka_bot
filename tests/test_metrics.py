from services import metrics


def test_increment_and_snapshot():
    metrics.reset()
    metrics.increment("spam_deleted_link")
    metrics.increment("spam_deleted_link")
    metrics.increment("autobans", 3)

    snap = metrics.snapshot()
    assert snap["counters"]["spam_deleted_link"] == 2
    assert snap["counters"]["autobans"] == 3
    assert "uptime_seconds" in snap
    assert snap["uptime_seconds"] >= 0


def test_unknown_counter_starts_at_zero():
    metrics.reset()
    counters = metrics.get_counters()
    assert counters == {}


def test_reset_clears_counters():
    metrics.increment("messages_seen")
    metrics.reset()
    assert metrics.get_counters() == {}
