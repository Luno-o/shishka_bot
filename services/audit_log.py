"""
Lightweight in-memory log of messages removed by automatic moderation.

Purely diagnostic - lets an admin run !falsepositives and see the last few
auto-deletions in this chat (who, why, a text snippet) without digging
through the logs channel or the server. Deliberately not persisted: it
resets on restart, same trade-off as services/metrics.py.
"""
from collections import deque
from dataclasses import dataclass
from datetime import datetime

MAX_ENTRIES = 300
_SNIPPET_LIMIT = 120


@dataclass
class DeletionEntry:
    chat_id: int
    user_id: int
    reason: str
    snippet: str
    at: datetime


_log: deque[DeletionEntry] = deque(maxlen=MAX_ENTRIES)


def _make_snippet(text: str | None) -> str:
    if not text:
        return "[без текста]"
    snippet = " ".join(text.split())
    if len(snippet) > _SNIPPET_LIMIT:
        snippet = snippet[: _SNIPPET_LIMIT - 1] + "…"
    return snippet


def record_deletion(chat_id: int, user_id: int, reason: str, text: str | None = None) -> None:
    """Record one auto-deleted message. Call this alongside metrics.increment()."""
    _log.append(DeletionEntry(chat_id, user_id, reason, _make_snippet(text), datetime.now()))


def get_recent(chat_id: int, limit: int = 10) -> list[DeletionEntry]:
    """Most recent deletions for one chat, newest first."""
    matches = [entry for entry in _log if entry.chat_id == chat_id]
    return list(reversed(matches[-limit:]))


def reset() -> None:
    """Clear the log (tests only)."""
    _log.clear()
