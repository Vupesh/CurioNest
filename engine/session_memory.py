import os
import psycopg2


class SessionMemoryService:

    def __init__(self):

        self.conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        self.conn.autocommit = True

    # ==========================
    # STORE MESSAGE
    # ==========================

    def store_message(self, session_id, role, message):

        try:

            cursor = self.conn.cursor()

            cursor.execute(
                """
                INSERT INTO conversation_messages
                (session_id, role, message)
                VALUES (%s,%s,%s)
                """,
                (session_id, role, message)
            )

            cursor.close()

        except Exception as e:

            print("SESSION MEMORY STORE ERROR:", e)

    # ==========================
    # GET RECENT MESSAGES
    # ==========================

    def get_recent_messages(self, session_id, limit=10):

        try:

            cursor = self.conn.cursor()

            cursor.execute(
                """
                SELECT role, message
                FROM conversation_messages
                WHERE session_id=%s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (session_id, limit)
            )

            rows = cursor.fetchall()

            cursor.close()

            rows.reverse()

            return [
                {"role": r[0], "message": r[1]}
                for r in rows
            ]

        except Exception as e:

            print("SESSION MEMORY FETCH ERROR:", e)

            return []