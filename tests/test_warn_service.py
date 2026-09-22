from types import SimpleNamespace

import pytest

from services.warn_service import (
    add_warning,
    clear_warnings,
    consequence_for,
    count_warnings,
    remove_latest_warning,
)


def _cfg(enabled=True, mute_1h_at=2, mute_1d_at=3, ban_at=4):
    return SimpleNamespace(enabled=enabled, mute_1h_at=mute_1h_at, mute_1d_at=mute_1d_at, ban_at=ban_at)


def test_consequence_for_thresholds(monkeypatch):
    from services import warn_service

    monkeypatch.setattr(warn_service.config, "warn", _cfg())

    assert consequence_for(0) is None
    assert consequence_for(1) is None
    assert consequence_for(2) == "mute_1h"
    assert consequence_for(3) == "mute_1d"
    assert consequence_for(4) == "ban"
    # jumping several warnings at once still lands on the worst consequence
    assert consequence_for(10) == "ban"


def test_consequence_for_disabled(monkeypatch):
    from services import warn_service

    monkeypatch.setattr(warn_service.config, "warn", _cfg(enabled=False))
    assert consequence_for(999) is None


@pytest.mark.asyncio
async def test_add_and_count_warnings():
    chat_id, user_id, admin_id = -100111, 42, 7

    assert await count_warnings(chat_id, user_id) == 0

    total = await add_warning(chat_id, user_id, admin_id, "spam link")
    assert total == 1

    total = await add_warning(chat_id, user_id, admin_id, "spam again")
    assert total == 2

    assert await count_warnings(chat_id, user_id) == 2

    # warnings are scoped per-chat: a different chat starts fresh
    assert await count_warnings(-100222, user_id) == 0


@pytest.mark.asyncio
async def test_remove_latest_warning():
    chat_id, user_id, admin_id = -100111, 43, 7

    assert await remove_latest_warning(chat_id, user_id) is False

    await add_warning(chat_id, user_id, admin_id, "first")
    await add_warning(chat_id, user_id, admin_id, "second")
    assert await count_warnings(chat_id, user_id) == 2

    removed = await remove_latest_warning(chat_id, user_id)
    assert removed is True
    assert await count_warnings(chat_id, user_id) == 1


@pytest.mark.asyncio
async def test_clear_warnings():
    chat_id, user_id, admin_id = -100111, 44, 7

    await add_warning(chat_id, user_id, admin_id, "one")
    await add_warning(chat_id, user_id, admin_id, "two")
    await add_warning(chat_id, user_id, admin_id, "three")

    removed_count = await clear_warnings(chat_id, user_id)
    assert removed_count == 3
    assert await count_warnings(chat_id, user_id) == 0

    # clearing again is a safe no-op
    assert await clear_warnings(chat_id, user_id) == 0
