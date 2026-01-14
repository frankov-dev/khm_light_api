import mysql.connector
from app.core.config import settings

class DatabaseHandler:
    def __init__(self):
        self.db = mysql.connector.connect(
            host=settings.DB_HOST, user=settings.DB_USER,
            password=settings.DB_PASSWORD, database=settings.DB_NAME
        )
        self.cursor = self.db.cursor(dictionary=True)

    def save_data(self, data, target_date):
        # Видаляємо старе за конкретну дату
        self.cursor.execute("DELETE FROM schedules WHERE day_date = %s", (target_date,))
        query = """INSERT INTO schedules (queue_id, day_date, start_time, end_time, type) 
                   VALUES ((SELECT id FROM queues WHERE name = %s), %s, %s, %s, %s)"""
        for q, intervals in data.items():
            for i in intervals:
                self.cursor.execute(query, (q, target_date, i['start'], i['end'], i['type']))
        self.db.commit()

    def get_schedule(self, q_name, q_date):
        query = """SELECT start_time, end_time, type FROM schedules 
                   JOIN queues ON schedules.queue_id = queues.id 
                   WHERE queues.name = %s AND day_date = %s"""
        self.cursor.execute(query, (q_name, q_date))
        return self.cursor.fetchall()
