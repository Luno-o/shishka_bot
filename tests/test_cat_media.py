"""Shishka-only commands never show friends, friend commands never show Shishka."""
from datetime import date

import pytest
from aiogram.filters import Command

from db.models import CatPhoto, ShishTarotReading
from handlers import cat_commands
from services.cat_media import CATEGORY_FRIEND, CATEGORY_SHISHKA, random_media
from services.shish_tarot import get_daily_shishka


async def _add(file_id: str, category: str) -> CatPhoto:
    return await CatPhoto.objects.create(
        file_id=file_id, file_unique_id=f"u-{file_id}", added_by=1,
        media_type="photo", category=category,
    )


@pytest.mark.parametrize("category", [CATEGORY_SHISHKA, CATEGORY_FRIEND], ids=["shishka", "friend"])
@pytest.mark.asyncio
async def test_random_media_returns_only_requested_category(category):
    for i in range(5):
        await _add(f"s{i}", CATEGORY_SHISHKA)
        await _add(f"f{i}", CATEGORY_FRIEND)

    picks = {(await random_media(category)).category for _ in range(40)}

    assert picks == {category}


@pytest.mark.asyncio
async def test_random_media_none_when_category_empty():
    await _add("f", CATEGORY_FRIEND)
    assert await random_media(CATEGORY_SHISHKA) is None


@pytest.mark.asyncio
async def test_tarot_never_assigns_a_friend():
    await _add("s", CATEGORY_SHISHKA)
    for i in range(10):
        await _add(f"f{i}", CATEGORY_FRIEND)

    results = [await get_daily_shishka(uid, date(2026, 11, 20)) for uid in range(30)]

    assert {r.category for r in results} == {CATEGORY_SHISHKA}


@pytest.mark.asyncio
async def test_tarot_reassigns_stale_reading_pointing_to_friend():
    shishka = await _add("s", CATEGORY_SHISHKA)
    friend = await _add("f", CATEGORY_FRIEND)
    await ShishTarotReading.objects.create(user_id=5, reading_date="2026-11-20", cat_photo_id=friend.id)

    result = await get_daily_shishka(5, date(2026, 11, 20))

    assert result.id == shishka.id
    reading = await ShishTarotReading.objects.get(user_id=5, reading_date="2026-11-20")
    assert reading.cat_photo_id == shishka.id


@pytest.mark.asyncio
async def test_tarot_none_when_only_friends():
    await _add("f", CATEGORY_FRIEND)
    assert await get_daily_shishka(6, date(2026, 11, 20)) is None


def _commands_of(handler) -> set[str]:
    names: set[str] = set()
    for h in cat_commands.router.message.handlers:
        if h.callback is handler:
            for f in h.filters or []:
                if isinstance(f.callback, Command):
                    names.update(c if isinstance(c, str) else c.pattern for c in f.callback.commands)
    return names


@pytest.mark.parametrize(
    ("handler_name", "new", "legacy"),
    [
        ("send_random_friend_cat", {"shish_friends", "shish_friend", "shishfriend"}, {"shis_friends", "shis_friend", "shisfriend"}),
        ("add_friend_cat_media", {"add_shish_friend"}, {"add_shis_friend"}),
        ("submit_shish_friend", {"submit_shish_friend"}, {"submit_shis_friend"}),
    ],
    ids=["show", "add", "submit"],
)
def test_friend_commands_renamed_with_legacy_aliases(handler_name, new, legacy):
    commands = _commands_of(getattr(cat_commands, handler_name))
    assert new <= commands
    assert legacy <= commands  # old names keep working for members used to them


def test_help_and_menu_use_new_names_only():
    from pathlib import Path

    for path in ("locales/ru/strings.ftl", "locales/en/strings.ftl", "bot.py"):
        text = Path(path).read_text(encoding="utf-8")
        assert "shis_" not in text and "shisfriend" not in text, path
