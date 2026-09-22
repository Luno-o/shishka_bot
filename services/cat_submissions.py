"""
Pending cat-photo submissions from regular users (!submit_shishka /
!submit_shis_friend), awaiting an admin's approve/reject decision.

Mirrors the pending_messages pattern in handlers/personal_actions.py:
callback_data has a strict length limit and can't carry a full file_id, so
submissions are kept here keyed by a short id and only that id travels in
the inline button's callback_data.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, TypedDict

MAX_PENDING_SUBMISSIONS = 100
_EXPIRY = timedelta(hours=6)


class PendingSubmission(TypedDict):
    file_id: str
    file_unique_id: str
    media_type: str  # 'photo' or 'animation'
    category: str  # 'shishka' or 'friend'
    description: Optional[str]
    submitted_by: int
    submitted_at: datetime


_pending: dict[str, PendingSubmission] = {}


def _cleanup_old() -> None:
    """Drop expired entries and enforce the size cap (oldest first)."""
    now = datetime.now()
    expired = [k for k, v in _pending.items() if now - v["submitted_at"] > _EXPIRY]
    for k in expired:
        del _pending[k]

    while len(_pending) > MAX_PENDING_SUBMISSIONS:
        oldest_key = min(_pending, key=lambda k: _pending[k]["submitted_at"])
        del _pending[oldest_key]


def queue_submission(
    *,
    file_id: str,
    file_unique_id: str,
    media_type: str,
    category: str,
    description: Optional[str],
    submitted_by: int,
) -> str:
    """Store a pending submission and return its short lookup key."""
    _cleanup_old()
    key = uuid.uuid4().hex[:10]
    _pending[key] = {
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "media_type": media_type,
        "category": category,
        "description": description,
        "submitted_by": submitted_by,
        "submitted_at": datetime.now(),
    }
    return key


def peek_submission(key: str) -> Optional[PendingSubmission]:
    """Look up a pending submission without removing it."""
    return _pending.get(key)


def pop_submission(key: str) -> Optional[PendingSubmission]:
    """Remove and return a pending submission (used once decided)."""
    return _pending.pop(key, None)
