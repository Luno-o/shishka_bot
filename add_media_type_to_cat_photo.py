#!/usr/bin/env python3
"""
Скрипт для добавления поля media_type в таблицу cat_photos
Запускать: python migrate_media_type.py
"""

import sqlite3
import os
from pathlib import Path

def migrate():
    """Add media_type column to cat_photos table."""
    print("🔄 Начинаем миграцию...")
    
    # Пути к БД (проверяем несколько вариантов)
    db_paths = [
        "/root/shishka-bot/data/db.sqlite",
        "/root/shishka-bot/db.sqlite",
        "data/db.sqlite",
        "db.sqlite"
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ База данных не найдена! Проверьте пути:")
        for path in db_paths:
            print(f"  - {path}")
        return
    
    print(f"📁 Найдена БД: {db_path}")
    
    try:
        # Подключаемся к БД
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cat_photos'")
        if not cursor.fetchone():
            print("❌ Таблица cat_photos не существует!")
            conn.close()
            return
        
        # Проверяем существование колонки
        cursor.execute("PRAGMA table_info(cat_photos)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"📋 Текущие колонки: {', '.join(column_names)}")
        
        if 'media_type' not in column_names:
            print("📝 Добавляем колонку media_type...")
            
            # Добавляем колонку с дефолтным значением 'photo'
            cursor.execute(
                "ALTER TABLE cat_photos ADD COLUMN media_type VARCHAR(20) DEFAULT 'photo'"
            )
            conn.commit()
            print("✅ Колонка media_type добавлена")
        else:
            print("✅ Колонка media_type уже существует")
        
        # Обновляем существующие записи (если есть NULL)
        cursor.execute(
            "UPDATE cat_photos SET media_type = 'photo' WHERE media_type IS NULL"
        )
        conn.commit()
        
        # Проверяем результат
        cursor.execute("SELECT COUNT(*) FROM cat_photos")
        total = cursor.fetchone()[0]
        print(f"📊 Всего записей: {total}")
        
        cursor.execute("SELECT COUNT(*) FROM cat_photos WHERE media_type = 'photo'")
        photo_count = cursor.fetchone()[0]
        print(f"📸 Фото: {photo_count}")
        
        cursor.execute("SELECT COUNT(*) FROM cat_photos WHERE media_type = 'animation'")
        animation_count = cursor.fetchone()[0]
        print(f"🎬 Гифки: {animation_count}")
        
        # Показываем несколько записей для проверки
        cursor.execute("SELECT id, media_type, description FROM cat_photos LIMIT 5")
        rows = cursor.fetchall()
        if rows:
            print("\n📋 Примеры записей:")
            for row in rows:
                desc = row[2] or "без описания"
                print(f"  ID: {row[0]}, Тип: {row[1]}, Описание: {desc}")
        
        conn.close()
        print("\n✅ Миграция завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return

if __name__ == "__main__":
    migrate()