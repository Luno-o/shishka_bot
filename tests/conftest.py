import os
from pathlib import Path
from tempfile import gettempdir

import pytest
import pytest_asyncio

TEST_DB_PATH = Path(gettempdir()) / f"shishka-tests-{os.getpid()}.db"
os.environ["DB_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

from db import close_db, init_db  # noqa: E402
from db.database import ormar_config  # noqa: E402
from db.models import (  # noqa: E402
    CatPhoto,
    Member,
    PendingNewcomer,
    ShishTarotReading,
    Spam,
)

MODELS = (PendingNewcomer, ShishTarotReading, CatPhoto, Spam, Member)


@pytest.fixture(scope="session", autouse=True)
def remove_test_database():
    TEST_DB_PATH.unlink(missing_ok=True)
    yield
    TEST_DB_PATH.unlink(missing_ok=True)


@pytest_asyncio.fixture(autouse=True)
async def database():
    await init_db()
    for model in MODELS:
        await model.objects.delete(each=True)
    yield
    for model in MODELS:
        await model.objects.delete(each=True)
    await close_db()
    await ormar_config.engine.dispose()
