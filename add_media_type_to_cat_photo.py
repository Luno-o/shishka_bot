#!/usr/bin/env python3
"""
Скрипт для добавления поля media_type в таблицу cat_photos
Запускать: python add_media_type_to_cat_photo.py
"""

import asyncio
from tortoise import Tortoise
from config import settings

async def migrate():
    """Add media_type field to cat_photos table."""
    print("🔄 Начинаем миграцию...")
    
    # Подключаемся к БД
    await Tortoise.init(
        db_url=settings.DB_URL,
        modules={"models": ["db.models"]}
    )
    
    try:
        # Проверяем существование колонки
        from db.models import CatPhoto
        
        # Получаем информацию о таблице через raw SQL
        conn = Tortoise.get_connection("default")
        
        # SQLite
        if "sqlite" in settings.DB_URL:
            result = await conn.execute_query(
                "PRAGMA table_info(cat_photos)"
            )
            columns = [row[1] for row in result]  # row[1] это имя колонки
            
            if "media_type" not in columns:
                print("📝 Добавляем колонку media_type...")
                await conn.execute_query(
                    "ALTER TABLE cat_photos ADD COLUMN media_type VARCHAR(20) DEFAULT 'photo'"
                )
                print("✅ Колонка media_type добавлена")
            else:
                print("✅ Колонка media_type уже существует")
        
        # PostgreSQL
        elif "postgres" in settings.DB_URL:
            result = await conn.execute_query(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='cat_photos'
                """
            )
            columns = [row[0] for row in result]
            
            if "media_type" not in columns:
                print("📝 Добавляем колонку media_type...")
                await conn.execute_query(
                    "ALTER TABLE cat_photos ADD COLUMN media_type VARCHAR(20) DEFAULT 'photo'"
                )
                print("✅ Колонка media_type добавлена")
            else:
                print("✅ Колонка media_type уже существует")
        
        # Обновляем существующие записи (если есть NULL)
        await CatPhoto.filter(media_type__isnull=True).update(media_type='photo')
        
        print("✅ Миграция завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(migrate())