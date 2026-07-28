import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print('Таблицы в БД:')
for table in tables:
    print(f'  - {table[0]}')

conn.close()