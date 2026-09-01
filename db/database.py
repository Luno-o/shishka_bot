"""Database connection, schema creation, and idempotent migrations."""

import logging

import databases
import ormar
import sqlalchemy
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from config import config

logger = logging.getLogger(__name__)

DATABASE_URL = config.db.url

ormar_config = ormar.OrmarConfig(
    database=databases.Database(DATABASE_URL),
    metadata=sqlalchemy.MetaData(),
    engine=create_async_engine(DATABASE_URL),
)


def _add_missing_columns(connection: Connection) -> None:
    """Apply legacy SQLite migrations without deleting existing data."""
    if connection.dialect.name != "sqlite":
        return

    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    migrations = {
        "cat_photos": {
            "description": "VARCHAR(500)",
            "media_type": "VARCHAR(20) NOT NULL DEFAULT 'photo'",
        },
        "members": {
            "date": "DATETIME",
            "halloween_sweets": "INTEGER NOT NULL DEFAULT 0",
            "halloween_golden_tickets": "INTEGER NOT NULL DEFAULT 0",
        },
        "spam": {
            "is_blocked": "BOOLEAN NOT NULL DEFAULT 0",
            "date": "DATETIME",
            "chat_id": "BIGINT",
            "user_id": "BIGINT",
        },
    }

    for table_name, columns in migrations.items():
        if table_name not in tables:
            continue
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, definition in columns.items():
            if column_name in existing:
                continue
            connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}'))
            logger.info("Applied database migration: %s.%s", table_name, column_name)

    if "cat_photos" in tables:
        connection.execute(
            text("UPDATE cat_photos SET media_type = 'photo' WHERE media_type IS NULL OR media_type = ''")
        )
    if "members" in tables:
        connection.execute(text("UPDATE members SET date = CURRENT_TIMESTAMP WHERE date IS NULL"))
    if "spam" in tables:
        connection.execute(text("UPDATE spam SET date = CURRENT_TIMESTAMP WHERE date IS NULL"))


def _initialize_schema(connection: Connection) -> None:
    ormar_config.metadata.create_all(connection)
    _add_missing_columns(connection)


async def init_db() -> None:
    """Create the current schema, apply migrations, and open one DB connection."""
    # Importing the model package registers every table in shared metadata.
    import db.models  # noqa: F401

    async with ormar_config.engine.begin() as connection:
        await connection.run_sync(_initialize_schema)
    if not ormar_config.database.is_connected:
        await ormar_config.database.connect()
    logger.info("Database initialized")


async def close_db() -> None:
    if ormar_config.database.is_connected:
        await ormar_config.database.disconnect()
