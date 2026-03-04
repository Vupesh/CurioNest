import os
import psycopg2
from psycopg2.extras import RealDictCursor


class LeadPersistenceService:

    def __init__(self):

        self.db_config = {
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT"),
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
        }

    # --------------------------------
    # DB Connection
    # --------------------------------

    def get_connection(self):
        return psycopg2.connect(**self.db_config)

    # --------------------------------
    # Get existing lead by session
    # --------------------------------

    def get_lead_by_session(self, session_id):

        conn = self.get_connection()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:

                cur.execute(
                    """
                    SELECT *
                    FROM leads
                    WHERE session_id = %s
                    LIMIT 1
                    """,
                    (session_id,)
                )

                return cur.fetchone()

        finally:
            conn.close()

    # --------------------------------
    # Create new lead
    # --------------------------------

    def create_lead(
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
        status
    ):

        conn = self.get_connection()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:

                cur.execute(
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
                        status
                    )
                )

                lead_id = cur.fetchone()["id"]

                conn.commit()

                return lead_id

        finally:
            conn.close()

    # --------------------------------
    # Update existing lead
    # --------------------------------

    def update_lead(
        self,
        lead_id,
        escalation_code,
        escalation_reason,
        confidence,
        engagement_score,
        intent_strength,
        status
    ):

        conn = self.get_connection()

        try:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE leads
                    SET
                        escalation_code = %s,
                        escalation_reason = %s,
                        confidence = GREATEST(confidence, %s),
                        engagement_score = %s,
                        intent_strength = %s,
                        status = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        escalation_code,
                        escalation_reason,
                        confidence,
                        engagement_score,
                        intent_strength,
                        status,
                        lead_id
                    )
                )

                conn.commit()

        finally:
            conn.close()

    # --------------------------------
    # UPSERT Logic (Option A)
    # --------------------------------

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
        status
    ):

        existing = self.get_lead_by_session(session_id)

        if existing:

            lead_id = existing["id"]

            self.update_lead(
                lead_id,
                escalation_code,
                escalation_reason,
                confidence,
                engagement_score,
                intent_strength,
                status
            )

            return lead_id

        else:

            return self.create_lead(
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