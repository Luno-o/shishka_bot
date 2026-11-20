"""Random cat media by category: Shishka herself vs. her cat friends."""
import random

from db.models import CatPhoto

CATEGORY_SHISHKA = "shishka"
CATEGORY_FRIEND = "friend"


async def media_of(category: str) -> list[CatPhoto]:
    """Return all media of one category."""
    return await CatPhoto.objects.filter(category=category).all()


async def random_media(category: str) -> CatPhoto | None:
    """Return a random media of ``category``, or None if there is none."""
    media_list = await media_of(category)
    return random.choice(media_list) if media_list else None
