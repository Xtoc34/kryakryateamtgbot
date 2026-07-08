import sqlite3
from datetime import datetime
import os

DB_NAME = os.environ.get('DB_NAME', 'db.sqlite3')

def init_db():
    """Ініціалізація бази даних та створення таблиць"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            user_id INTEGER PRIMARY KEY,
            topic_id INTEGER
        )
    ''')

    # Оновлена таблиця блекліста з підтримкою кулдауну та статусів апеляції
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            user_id INTEGER PRIMARY KEY,
            banned_at TEXT,
            appeal_status TEXT DEFAULT 'none'
        )
    ''')

    conn.commit()
    conn.close()

def get_user_lang(user_id):
    """Отримати мову користувача"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT lang FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_user_lang(user_id, lang):
    """Зберегти або оновити мову користувача"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, lang) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang
    ''', (user_id, lang))
    conn.commit()
    conn.close()

def get_user_by_topic(topic_id):
    """Знайти user_id за ID топіка в групі"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM topics WHERE topic_id = ?', (topic_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_topic_by_user(user_id):
    """Знайти ID топіка за user_id"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT topic_id FROM topics WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_topic(user_id, topic_id):
    """Зберегти зв'язку користувача та топіка"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO topics (user_id, topic_id) VALUES (?, ?)', (user_id, topic_id))
    conn.commit()
    conn.close()

def delete_topic(user_id):
    """Видалити зв'язку при закритті тікета"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM topics WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# =====================================================================
# 🛡️ ОБНОВЛЕНА СИСТЕМА БАНІВ ТА АПЕЛЯЦІЙ
# =====================================================================

def is_banned(user_id):
    """Перевірити, чи забанений користувач"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM blacklist WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def add_to_blacklist(user_id):
    """Додати користувача в бан з фіксацією часу та статусу"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT OR REPLACE INTO blacklist (user_id, banned_at, appeal_status) 
        VALUES (?, ?, 'none')
    ''', (user_id, current_time))
    conn.commit()
    conn.close()

def remove_from_blacklist(user_id):
    """Видалити користувача з бану (розбанити)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blacklist WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_ban_info(user_id):
    """Отримати точну інформацію про бан (час та статус апеляції)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT banned_at, appeal_status FROM blacklist WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"banned_at": row[0], "appeal_status": row[1]}
    return None

def update_appeal_status(user_id, status):
    """Оновити статус апеляції (pending / rejected)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE blacklist SET appeal_status = ? WHERE user_id = ?', (status, user_id))
    conn.commit()
    conn.close()