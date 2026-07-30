"""
Безопасная инициализация базы данных.
Создает только отсутствующие таблицы и колонки.
"""

import asyncio
import logging
import sys
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from db.database import ormar_config
from db.models import Member, Spam
from db.models.cat_photo import CatPhoto


async def create_tables_only():
    """Создает только таблицы через Ormar."""
    try:
        logger.info("🔄 Создание таблиц через Ormar...")
        
        if not ormar_config.database.is_connected:
            await ormar_config.database.connect()
            logger.info("✅ Подключение к БД установлено")
        
        # Создаем таблицы (create_all не удаляет существующие)
        async with ormar_config.engine.begin() as conn:
            await conn.run_sync(ormar_config.metadata.create_all)
        
        logger.info("✅ Таблицы созданы (или уже существовали)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")
        raise
    finally:
        if ormar_config.database.is_connected:
            await ormar_config.database.disconnect()


def fix_cat_photos_table():
    """Исправляет структуру таблицы cat_photos через прямой SQLite."""
    try:
        logger.info("🔄 Проверка структуры cat_photos...")
        
        db_path = '/app/data/db.sqlite'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем, существует ли таблица
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cat_photos'")
        if not cursor.fetchone():
            logger.warning("⚠️ Таблица cat_photos не существует!")
            # Создаем таблицу с правильной структурой
            cursor.execute('''
                CREATE TABLE cat_photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    file_unique_id TEXT NOT NULL UNIQUE,
                    added_by INTEGER NOT NULL,
                    added_at REAL NOT NULL,
                    caption TEXT,
                    description TEXT
                )
            ''')
            conn.commit()
            logger.info("✅ Таблица cat_photos создана с правильной структурой")
            conn.close()
            return
        
        # Получаем текущие колонки
        cursor.execute("PRAGMA table_info(cat_photos)")
        columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"📋 Текущие колонки: {columns}")
        
        # Проверяем наличие колонки description
        if 'description' not in columns:
            logger.warning("⚠️ Колонка description отсутствует, добавляем...")
            try:
                cursor.execute("ALTER TABLE cat_photos ADD COLUMN description TEXT")
                conn.commit()
                logger.info("✅ Колонка description добавлена")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e):
                    logger.info("ℹ️ Колонка description уже существует")
                else:
                    logger.error(f"❌ Ошибка: {e}")
        else:
            logger.info("✅ Колонка description уже существует")
        
        # Проверяем наличие колонки caption
        if 'caption' not in columns:
            logger.warning("⚠️ Колонка caption отсутствует, добавляем...")
            try:
                cursor.execute("ALTER TABLE cat_photos ADD COLUMN caption TEXT")
                conn.commit()
                logger.info("✅ Колонка caption добавлена")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e):
                    logger.info("ℹ️ Колонка caption уже существует")
                else:
                    logger.error(f"❌ Ошибка: {e}")
        else:
            logger.info("✅ Колонка caption уже существует")
        
        conn.close()
        logger.info("✅ Структура cat_photos в порядке")
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки структуры: {e}")
        raise


if __name__ == "__main__":
    try:
        # Шаг 1: Создаем таблицы через Ormar
        asyncio.run(create_tables_only())
        
        # Шаг 2: Исправляем структуру cat_photos
        fix_cat_photos_table()
        
        logger.info("✅ Инициализация завершена успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        sys.exit(1)