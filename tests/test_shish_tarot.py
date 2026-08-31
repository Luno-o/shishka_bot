import asyncio
from datetime import date

import pytest

from db.models import CatPhoto, ShishTarotReading
from services.shish_tarot import get_daily_shishka


async def add_photo(file_id: str) -> CatPhoto:
    return await CatPhoto.objects.create(
        file_id=file_id,
        file_unique_id=f"unique-{file_id}",
        added_by=1,
        media_type="photo",
    )


@pytest.mark.asyncio
async def test_same_user_gets_same_shishka_for_the_day():
    await add_photo("one")
    await add_photo("two")

    first = await get_daily_shishka(42, date(2026, 8, 31))
    second = await get_daily_shishka(42, date(2026, 8, 31))

    assert first.id == second.id
    assert await ShishTarotReading.objects.filter(user_id=42).count() == 1


@pytest.mark.asyncio
async def test_concurrent_requests_create_one_assignment():
    await add_photo("one")
    await add_photo("two")

    results = await asyncio.gather(
        *(get_daily_shishka(77, date(2026, 8, 31)) for _ in range(20))
    )

    assert len({result.id for result in results}) == 1
    assert await ShishTarotReading.objects.filter(user_id=77).count() == 1
