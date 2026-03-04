import os
import psycopg2
from services.logging_service import LoggingService
from engine.event_logger import EventLogger


class LeadPersistenceService:

    def __init__(self):

        self.logger = LoggingService()

        try:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT"),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
            )

            self.conn.autocommit = True

        except Exception as e:
            self.logger.log("DB_CONNECTION_ERROR", str(e))
            self.conn = None

        # Event Logger
        self.event_logger = EventLogger()

    # =============================
    # UPSERT LEAD
    # =============================

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
        status,
    ):

        if not self.conn:
            self.logger.log("DB_CONNECTION_MISSING", "Cannot persist lead")
            return None

        try:

            cursor = self.conn.cursor()

            cursor.execute(
                """
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
                RETURNING id
                """,
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

            lead_id = cursor.fetchone()[0]

            cursor.close()

            # =============================
            # EVENT LOGGING
            # =============================

            try:
                self.event_logger.log_event(
                    lead_id,
                    session_id,
                    "ESCALATION",
                    escalation_code,
                    confidence,
                    engagement_score,
                )
            except Exception as event_error:
                self.logger.log("EVENT_LOGGING_FAILED", str(event_error))

            return lead_id

        except Exception as e:

            self.logger.log("LEAD_PERSISTENCE_ERROR", str(e))
            return None