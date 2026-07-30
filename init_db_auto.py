# init_db_auto.py
import logging
from db.database import engine
from db.models.member import Member
from db.models.spam import SpamRecord
# ГЛАВНОЕ: импортируем модель для фото кошек из вашего форка
from db.models.cat_photo import CatPhoto

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    logger.info("🔄 Начинаю проверку и создание таблиц БД...")
    try:
        # Создает таблицы для ВСЕХ импортированных моделей
        # Если таблица уже есть, она не будет пересоздана
        Member.metadata.create_all(engine)
        logger.info("✅ Таблицы успешно созданы (или уже существовали).")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}")
        raise

if __name__ == "__main__":
    init_database()