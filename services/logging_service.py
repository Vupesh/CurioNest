import sqlite3
from datetime import datetime

class LoggingService:

    def __init__(self, db_path="curionest_logs.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            details TEXT
        )
        """)

        conn.commit()
        conn.close()

    def log(self, event_type, details):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO logs (timestamp, event_type, details)
        VALUES (?, ?, ?)
        """, (datetime.utcnow().isoformat(), event_type, str(details)))

        conn.commit()
        conn.close()
