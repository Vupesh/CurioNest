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

        self.event_logger = EventLogger()

    # =============================
    # UPSERT LEAD (SESSION SAFE + SCORE EVOLUTION)
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

            # 1️⃣ Check if lead already exists for session

            cursor.execute(
                """
                SELECT id, confidence
                FROM leads
                WHERE session_id = %s
                LIMIT 1
                """,
                (session_id,),
            )

            existing = cursor.fetchone()

            if existing:

                lead_id = existing[0]
                existing_confidence = existing[1]

                # 2️⃣ Update lead if new signal is stronger

                if confidence > existing_confidence:

                    cursor.execute(
                        """
                        UPDATE leads
                        SET confidence = %s,
                            escalation_code = %s,
                            escalation_reason = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            confidence,
                            escalation_code,
                            escalation_reason,
                            lead_id,
                        ),
                    )

                    self.logger.log(
                        "LEAD_CONFIDENCE_UPDATED",
                        {
                            "session_id": session_id,
                            "old_confidence": existing_confidence,
                            "new_confidence": confidence,
                        },
                    )

            else:

                # 3️⃣ Create new lead

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

                self.logger.log(
                    "LEAD_CREATED",
                    {
                        "session_id": session_id,
                        "confidence": confidence,
                    },
                )

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

    # =============================
    # SAVE CONTACT DETAILS
    # =============================

    def save_contact(self, lead_id, name=None, email=None, phone=None):

        if not self.conn:
            self.logger.log("DB_CONNECTION_MISSING", "Cannot persist contact")
            return False

        try:

            cursor = self.conn.cursor()

            cursor.execute(
                """
                INSERT INTO lead_contacts (
                    lead_id,
                    name,
                    email,
                    phone
                )
                VALUES (%s,%s,%s,%s)
                """,
                (
                    lead_id,
                    name,
                    email,
                    phone,
                ),
            )

            cursor.close()

            self.logger.log(
                "CONTACT_CAPTURED",
                {
                    "lead_id": str(lead_id),
                    "email": email,
                    "phone": phone,
                },
            )

            return True

        except Exception as e:

            self.logger.log("CONTACT_SAVE_ERROR", str(e))
            return False
            