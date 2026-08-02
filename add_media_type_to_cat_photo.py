#!/usr/bin/env python3
"""
Скрипт для добавления поля media_type в таблицу cat_photos
Запускать: python add_media_type_column.py
"""

import asyncio
from db.database import database
from db.models import CatPhoto

async def add_media_type_column():
    """Add media_type column to cat_photos table."""
    print("🔄 Начинаем миграцию...")
    
    try:
        # Проверяем существование колонки через PRAGMA
        # Получаем информацию о таблице
        conn = database._connection
        cursor = await conn.execute("PRAGMA table_info(cat_photos)")
        columns = await cursor.fetchall()
        
        column_names = [col[1] for col in columns]  # Второй элемент - имя колонки
        
        if 'media_type' not in column_names:
            print("📝 Добавляем колонку media_type...")
            await conn.execute(
                "ALTER TABLE cat_photos ADD COLUMN media_type VARCHAR(20) DEFAULT 'photo'"
            )
            print("✅ Колонка media_type добавлена")
        else:
            print("✅ Колонка media_type уже существует")
        
        # Обновляем существующие записи (если есть NULL)
        await CatPhoto.objects.filter(media_type__isnull=True).update(media_type='photo')
        
        print("✅ Миграция завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")

if __name__ == "__main__":
    asyncio.run(add_media_type_column())