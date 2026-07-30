# init_db_safe.py
"""
Безопасная инициализация базы данных.
Создает только отсутствующие таблицы, не удаляя существующие данные.
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импортируем ВСЕ модели, включая новую CatPhoto
from db.database import ormar_config
from db.models import Member, Spam
from db.models.cat_photo import CatPhoto  # <-- КРИТИЧНО ВАЖНО


async def create_tables_if_not_exist() -> None:
    """Создает только отсутствующие таблицы."""
    logger.info("🔄 Проверка и создание таблиц...")
    
    try:
        # Подключаемся к БД
        if not ormar_config.database.is_connected:
            await ormar_config.database.connect()
            logger.info("✅ Подключение к БД установлено")
        
        # Создаем таблицы (create_all не удаляет существующие)
        async with ormar_config.engine.begin() as conn:
            await conn.run_sync(ormar_config.metadata.create_all)
        
        logger.info("✅ Все таблицы созданы (или уже существовали)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}")
        raise
    finally:
        # Закрываем соединения
        if ormar_config.database.is_connected:
            await ormar_config.database.disconnect()
        await ormar_config.engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(create_tables_if_not_exist())
        logger.info("✅ Инициализация завершена успешно")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        sys.exit(1)