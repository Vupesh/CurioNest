import os
import psycopg2


class EventLogger:

    def __init__(self):

        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )

        self.conn.autocommit = True

    def log_event(
        self,
        lead_id,
        session_id,
        event_type,
        event_code,
        confidence,
        engagement_score
    ):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO lead_events (
                lead_id,
                session_id,
                event_type,
                event_code,
                confidence,
                engagement_score
            )
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (
                lead_id,
                session_id,
                event_type,
                event_code,
                confidence,
                engagement_score
            )
        )

        cursor.close()