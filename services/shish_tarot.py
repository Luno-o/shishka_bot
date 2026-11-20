"""Daily Shish-tarot selection backed by the existing cat media database."""

import asyncio
import random
from datetime import date, datetime
from zoneinfo import ZoneInfo

import ormar

from config import config
from db.models import CatPhoto, ShishTarotReading
from services.cat_media import CATEGORY_SHISHKA, media_of

_assignment_lock = asyncio.Lock()


async def get_daily_shishka(user_id: int, reading_date: date | None = None) -> CatPhoto | None:
    """Return the Shishka media assigned to a user for a day, creating it if needed (never a cat friend)."""
    day = (reading_date or datetime.now(ZoneInfo(config.bot.timezone)).date()).isoformat()

    async with _assignment_lock:
        try:
            reading = await ShishTarotReading.objects.get(
                user_id=user_id,
                reading_date=day,
            )
        except ormar.NoMatch:
            reading = None

        if reading:
            try:
                media = await CatPhoto.objects.get(id=reading.cat_photo_id)
                # Why: readings made before the category filter may point to a
                # cat friend; the tarot shows Shishka only, so pick again.
                if media.category == CATEGORY_SHISHKA:
                    return media
            except ormar.NoMatch:
                pass

        media_list = await media_of(CATEGORY_SHISHKA)
        if not media_list:
            return None

        media = random.choice(media_list)
        if reading:
            reading.cat_photo_id = media.id
            await reading.update()
        else:
            try:
                await ShishTarotReading.objects.create(
                    user_id=user_id,
                    reading_date=day,
                    cat_photo_id=media.id,
                )
            except Exception:
                concurrent_reading = await ShishTarotReading.objects.get(
                    user_id=user_id,
                    reading_date=day,
                )
                try:
                    concurrent_media = await CatPhoto.objects.get(
                        id=concurrent_reading.cat_photo_id
                    )
                    return concurrent_media
                except ormar.NoMatch:
                    pass
        return media
