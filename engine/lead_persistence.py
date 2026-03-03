import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from services.logging_service import LoggingService


class LeadPersistenceService:

    def __init__(self):
        self.logger = LoggingService()

        self.db_config = {
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT"),
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
        }

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = psycopg2.connect(**self.db_config)
            yield conn
        except Exception as e:
            self.logger.log("DB_CONNECTION_ERROR", {"error": str(e)})
            raise
        finally:
            if conn:
                conn.close()

    def upsert_lead(
        self,
        session_id,
        subject,
        chapter,
        question,
        escalation_code,
        escalation_reason,
        confidence,
        engagement_score,
        intent_strength,
        status="NEW"
    ):

        query = """
        INSERT INTO leads (
            session_id,
            subject,
            chapter,
            question,
            escalation_code,
            escalation_reason,
            confidence,
            engagement_score,
            intent_strength,
            status
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id;
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        query,
                        (
                            session_id,
                            subject,
                            chapter,
                            question,
                            escalation_code,
                            escalation_reason,
                            confidence,
                            engagement_score,
                            intent_strength,
                            status,
                        ),
                    )
                    lead_id = cur.fetchone()["id"]
                    conn.commit()

                    self.logger.log(
                        "LEAD_PERSISTED",
                        {
                            "lead_id": str(lead_id),
                            "session_id": session_id,
                            "status": status,
                        },
                    )

                    return lead_id

        except Exception as e:
            self.logger.log("LEAD_PERSISTENCE_ERROR", {"error": str(e)})
            return None