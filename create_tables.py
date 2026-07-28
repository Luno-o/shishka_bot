import sqlite3

# Подключаемся к БД
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Создаём таблицу members
cursor.execute('''
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    username TEXT,
    status TEXT,
    reputation_points INTEGER DEFAULT 0,
    messages_count INTEGER DEFAULT 0,
    violations_count_spam INTEGER DEFAULT 0,
    violations_count_profanity INTEGER DEFAULT 0
)
''')

# Создаём таблицу spam
cursor.execute('''
CREATE TABLE IF NOT EXISTS spam (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT,
    user_id INTEGER,
    chat_id INTEGER,
    is_spam INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
conn.close()

print("✅ Таблицы созданы!")