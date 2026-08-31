import os

import pytest_asyncio

os.environ["DB_URL"] = "sqlite+aiosqlite:///test_shishka.db"

from db import close_db, init_db
from db.models import CatPhoto, PendingNewcomer, ShishTarotReading


@pytest_asyncio.fixture(autouse=True)
async def database():
    await init_db()
    await PendingNewcomer.objects.delete(each=True)
    await ShishTarotReading.objects.delete(each=True)
    await CatPhoto.objects.delete(each=True)
    yield
    await PendingNewcomer.objects.delete(each=True)
    await ShishTarotReading.objects.delete(each=True)
    await CatPhoto.objects.delete(each=True)
    await close_db()
