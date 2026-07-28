import os
from config import config
from db.database import ormar_config

print("=" * 50)
print("Проверка конфигурации БД")
print("=" * 50)

print(f"1. config.db.url = {config.db.url}")
print(f"2. Текущая директория: {os.getcwd()}")
print(f"3. ormar_config.database.url = {ormar_config.database.url}")

# Проверяем, есть ли доступ на запись
try:
    with open('test_write.txt', 'w') as f:
        f.write('test')
    os.remove('test_write.txt')
    print("4. ✅ Права на запись есть")
except Exception as e:
    print(f"4. ❌ Нет прав на запись: {e}")

# Проверяем, что за URL
url = str(ormar_config.database.url)
if url.startswith('sqlite:///'):
    db_path = url.replace('sqlite:///', '')
    abs_path = os.path.abspath(db_path)
    print(f"5. Путь к БД из URL: {db_path}")
    print(f"6. Абсолютный путь: {abs_path}")
    print(f"7. Директория существует: {os.path.exists(os.path.dirname(abs_path))}")