"""
Database module for Khmelnytskyi Outage API.

Manages SQLite database with outage schedules and operational messages.
Uses separate connection per request for thread-safety with FastAPI.
"""

import sqlite3
from datetime import datetime
from typing import Optional


class Database:
    """
    SQLite database handler for outage schedules.
    
    Tables:
        - queues: Queue names (1.1 - 6.2)
        - schedules: Outage intervals per queue/date
        - daily_messages: Operational messages per date (general, not per-queue)
        - metadata: System metadata (last_updated, etc.)
    
    Thread Safety:
        Creates a new connection for each operation to ensure thread safety
        when used with FastAPI's async request handling.
    """
    
    def __init__(self, db_path: str = "outages.db") -> None:
        """
        Initialize database.
        
        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._init_db()
    
    def _connect(self) -> sqlite3.Connection:
        """Create a new connection (thread-safe for FastAPI)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._connect() as conn:
            conn.executescript("""
                -- Queue names dictionary (1.1 - 6.2)
                CREATE TABLE IF NOT EXISTS queues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                );
                
                -- Outage intervals
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    queue_id INTEGER NOT NULL,
                    day_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    type TEXT DEFAULT 'base',
                    FOREIGN KEY (queue_id) REFERENCES queues(id)
                );
                
                -- Operational messages (one per date, for all queues)
                CREATE TABLE IF NOT EXISTS daily_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day_date TEXT UNIQUE NOT NULL,
                    message TEXT NOT NULL
                );
                
                -- System metadata
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                
                -- Indexes for fast lookups
                CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(day_date);
                CREATE INDEX IF NOT EXISTS idx_schedules_queue_date ON schedules(queue_id, day_date);
            """)
            
            # Seed default queues (1.1 - 6.2)
            queues = [f"{i}.{j}" for i in range(1, 7) for j in range(1, 3)]
            conn.executemany(
                "INSERT OR IGNORE INTO queues (name) VALUES (?)",
                [(q,) for q in queues]
            )
            conn.commit()
    
    def save_schedule(
        self,
        date: str,
        schedules: dict,
        message: Optional[str] = None
    ) -> None:
        """
        Save schedule data for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
            schedules: Dict {queue: [{"start": "HH:MM", "end": "HH:MM", "type": "base"}]}
            message: Optional operational message for the date
        """
        with self._connect() as conn:
            # Clear old data for this date
            conn.execute("DELETE FROM schedules WHERE day_date = ?", (date,))
            conn.execute("DELETE FROM daily_messages WHERE day_date = ?", (date,))
            
            # Insert schedules
            for queue_name, intervals in schedules.items():
                for interval in intervals:
                    conn.execute(
                        """INSERT INTO schedules (queue_id, day_date, start_time, end_time, type)
                           VALUES ((SELECT id FROM queues WHERE name = ?), ?, ?, ?, ?)""",
                        (queue_name, date, interval["start"], interval["end"], 
                         interval.get("type", "base"))
                    )
            
            # Insert operational message
            if message and message.strip():
                conn.execute(
                    "INSERT INTO daily_messages (day_date, message) VALUES (?, ?)",
                    (date, message.strip())
                )
            
            # Update last_updated timestamp
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("last_updated", datetime.now().isoformat())
            )
            conn.commit()
    
    def get_schedule(self, queue: str, date: str) -> list[dict]:
        """
        Get schedule intervals for a queue on a specific date.
        
        Args:
            queue: Queue name (e.g., "3.1")
            date: Date in YYYY-MM-DD format
        
        Returns:
            List of dicts with start_time, end_time, type keys.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """SELECT start_time, end_time, type FROM schedules
                   JOIN queues ON schedules.queue_id = queues.id
                   WHERE queues.name = ? AND day_date = ?
                   ORDER BY start_time""",
                (queue, date)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_schedules(self, date: str) -> dict[str, list[dict]]:
        """
        Get all schedules for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
        
        Returns:
            Dict mapping queue names to lists of intervals.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """SELECT queues.name as queue, start_time, end_time, type
                   FROM schedules
                   JOIN queues ON schedules.queue_id = queues.id
                   WHERE day_date = ?
                   ORDER BY queues.name, start_time""",
                (date,)
            )
            
            result = {}
            for row in cursor.fetchall():
                queue = row["queue"]
                if queue not in result:
                    result[queue] = []
                result[queue].append({
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "type": row["type"]
                })
            return result
    
    def get_message(self, date: str) -> Optional[str]:
        """
        Get operational message for a date.
        
        Args:
            date: Date in YYYY-MM-DD format
        
        Returns:
            Message text or None if not found.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT message FROM daily_messages WHERE day_date = ?",
                (date,)
            )
            row = cursor.fetchone()
            return row["message"] if row else None
    
    def get_dates(self) -> list[str]:
        """
        Get list of available dates.
        
        Returns:
            List of dates in YYYY-MM-DD format, sorted descending.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT day_date FROM schedules ORDER BY day_date DESC"
            )
            return [row["day_date"] for row in cursor.fetchall()]
    
    def get_metadata(self, key: str) -> Optional[str]:
        """
        Get metadata value by key.
        
        Args:
            key: Metadata key (e.g., "last_updated")
        
        Returns:
            Value or None if not found.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT value FROM metadata WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            return row["value"] if row else None
