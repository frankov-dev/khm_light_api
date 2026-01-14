# app/db/database.py
import sqlite3
from datetime import datetime

class DatabaseHandler:
    def __init__(self, db_path="outages.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        # В SQLite з'єднання краще створювати для кожного запиту в багатопотоковому FastAPI
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Щоб отримувати дані як словники
        return conn

    def _init_db(self):
        """Створює таблиці, якщо їх немає"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    queue_id INTEGER,
                    day_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    type TEXT,
                    FOREIGN KEY (queue_id) REFERENCES queues(id)
                )
            """)
            # Заповнюємо черги за замовчуванням
            queues = [f"{i}.{j}" for i in range(1, 7) for j in range(1, 3)]
            conn.executemany("INSERT OR IGNORE INTO queues (name) VALUES (?)", [(q,) for q in queues])
            conn.commit()

    def save_data(self, data, target_date):
        with self._get_connection() as conn:
            # Видаляємо старі дані за цю дату
            conn.execute("DELETE FROM schedules WHERE day_date = ?", (target_date,))
            
            query = """INSERT INTO schedules (queue_id, day_date, start_time, end_time, type) 
                       VALUES ((SELECT id FROM queues WHERE name = ?), ?, ?, ?, ?)"""
            
            for q, intervals in data.items():
                for i in intervals:
                    conn.execute(query, (q, target_date, i['start'], i['end'], i['type']))
            conn.commit()

    def get_schedule(self, q_name, q_date):
        with self._get_connection() as conn:
            query = """SELECT start_time, end_time, type FROM schedules 
                       JOIN queues ON schedules.queue_id = queues.id 
                       WHERE queues.name = ? AND day_date = ?"""
            cursor = conn.execute(query, (q_name, q_date))
            return [dict(row) for row in cursor.fetchall()]