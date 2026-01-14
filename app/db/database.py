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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (queue_id) REFERENCES queues(id)
                )
            """)
            # Індекс для швидкого пошуку
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedules_date 
                ON schedules(day_date)
            """)
            # Заповнюємо черги за замовчуванням
            queues = [f"{i}.{j}" for i in range(1, 7) for j in range(1, 3)]
            conn.executemany("INSERT OR IGNORE INTO queues (name) VALUES (?)", [(q,) for q in queues])
            conn.commit()

    def save_data(self, data, target_date):
        """Зберігає графік для дати"""
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
        """Отримує графік для черги на дату"""
        with self._get_connection() as conn:
            query = """SELECT start_time, end_time, type FROM schedules 
                       JOIN queues ON schedules.queue_id = queues.id 
                       WHERE queues.name = ? AND day_date = ?
                       ORDER BY start_time"""
            cursor = conn.execute(query, (q_name, q_date))
            return [dict(row) for row in cursor.fetchall()]

    def get_available_dates(self):
        """Повертає список всіх дат, для яких є дані"""
        with self._get_connection() as conn:
            query = "SELECT DISTINCT day_date FROM schedules ORDER BY day_date DESC"
            cursor = conn.execute(query)
            return [row['day_date'] for row in cursor.fetchall()]
    
    def get_all_schedules_for_date(self, q_date):
        """Отримує всі графіки на дату"""
        with self._get_connection() as conn:
            query = """SELECT queues.name as queue, start_time, end_time, type 
                       FROM schedules 
                       JOIN queues ON schedules.queue_id = queues.id 
                       WHERE day_date = ?
                       ORDER BY queues.name, start_time"""
            cursor = conn.execute(query, (q_date,))
            
            result = {}
            for row in cursor.fetchall():
                queue = row['queue']
                if queue not in result:
                    result[queue] = []
                result[queue].append({
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'type': row['type']
                })
            return result