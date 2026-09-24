"""
Lightweight in-process counters, exposed as JSON via the healthcheck
server's /metrics endpoint (see services/healthcheck.py).

Deliberately simple (a dict in memory, reset on restart) rather than a
full Prometheus client - enough to see at a glance whether the bot is
doing anything, without adding a dependency.
"""
import time
from collections import defaultdict

_start_time = time.time()
_counters: dict[str, int] = defaultdict(int)


def increment(name: str, amount: int = 1) -> None:
    """Bump a named counter. Counters are created on first use, starting at 0."""
    _counters[name] += amount


def get_counters() -> dict[str, int]:
    """Snapshot of all counters (sorted for stable JSON output)."""
    return dict(sorted(_counters.items()))


def get_uptime_seconds() -> float:
    return time.time() - _start_time


def snapshot() -> dict:
    """Full metrics payload for the /metrics endpoint."""
    return {
        "uptime_seconds": round(get_uptime_seconds(), 1),
        "counters": get_counters(),
    }


def reset() -> None:
    """Clear all counters (useful for tests)."""
    _counters.clear()


def to_prometheus_text() -> str:
    """
    Same counters as snapshot(), rendered as Prometheus text exposition
    format (for a Grafana/Prometheus scrape instead of the plain-JSON
    /metrics - see /metrics/prometheus in services/healthcheck.py).
    """
    lines = [
        "# HELP shishka_bot_uptime_seconds Seconds since the bot process started.",
        "# TYPE shishka_bot_uptime_seconds gauge",
        f"shishka_bot_uptime_seconds {get_uptime_seconds():.1f}",
        "# HELP shishka_bot_events_total Named event counters (messages, spam, bans, warnings, ...).",
        "# TYPE shishka_bot_events_total counter",
    ]
    for name, value in get_counters().items():
        lines.append(f'shishka_bot_events_total{{name="{name}"}} {value}')
    return "\n".join(lines) + "\n"
