from datetime import datetime, timedelta

from services import cat_submissions
from services.cat_submissions import peek_submission, pop_submission, queue_submission


def _clear():
    cat_submissions._pending.clear()


def test_queue_and_pop_submission():
    _clear()
    key = queue_submission(
        file_id="FID1", file_unique_id="UID1", media_type="photo",
        category="shishka", description="cute", submitted_by=111,
    )

    sub = peek_submission(key)
    assert sub is not None
    assert sub["file_id"] == "FID1"
    assert sub["category"] == "shishka"
    assert sub["submitted_by"] == 111

    popped = pop_submission(key)
    assert popped == sub

    # once popped, it's gone
    assert peek_submission(key) is None
    assert pop_submission(key) is None


def test_unknown_key_returns_none():
    _clear()
    assert peek_submission("does-not-exist") is None
    assert pop_submission("does-not-exist") is None


def test_expired_submissions_are_cleaned_up():
    _clear()
    key = queue_submission(
        file_id="FID2", file_unique_id="UID2", media_type="animation",
        category="friend", description=None, submitted_by=222,
    )
    # simulate the submission having been queued long ago
    cat_submissions._pending[key]["submitted_at"] = datetime.now() - timedelta(hours=100)

    # queuing a new submission triggers cleanup of expired entries
    queue_submission(
        file_id="FID3", file_unique_id="UID3", media_type="photo",
        category="friend", description=None, submitted_by=333,
    )

    assert peek_submission(key) is None


def test_pending_size_is_capped():
    _clear()
    original_max = cat_submissions.MAX_PENDING_SUBMISSIONS
    cat_submissions.MAX_PENDING_SUBMISSIONS = 3
    try:
        keys = [
            queue_submission(
                file_id=f"FID{i}", file_unique_id=f"UID{i}", media_type="photo",
                category="shishka", description=None, submitted_by=i,
            )
            for i in range(5)
        ]
        assert len(cat_submissions._pending) <= 3
        # the oldest entries should have been evicted first
        assert peek_submission(keys[0]) is None
        assert peek_submission(keys[-1]) is not None
    finally:
        cat_submissions.MAX_PENDING_SUBMISSIONS = original_max
