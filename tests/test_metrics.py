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


def test_prometheus_text_contains_help_type_and_values():
    metrics.reset()
    metrics.increment("autobans", 2)

    text = metrics.to_prometheus_text()

    assert "# HELP shishka_bot_uptime_seconds" in text
    assert "# TYPE shishka_bot_events_total counter" in text
    assert 'shishka_bot_events_total{name="autobans"} 2' in text
    assert text.endswith("\n")


def test_prometheus_text_with_no_counters_still_has_uptime():
    metrics.reset()
    text = metrics.to_prometheus_text()
    assert "shishka_bot_uptime_seconds" in text
    assert "shishka_bot_events_total{" not in text
