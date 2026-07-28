import sqlite3

def add_table():
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cat_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            file_unique_id TEXT NOT NULL UNIQUE,
            added_by INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Таблица cat_photos создана!")

if __name__ == "__main__":
    add_table()