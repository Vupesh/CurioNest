import os
import psycopg2
from psycopg2.extras import RealDictCursor


class IdentityEngine:

    def __init__(self):

        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )

    # ================================
    # Resolve or Create Identity
    # ================================

    def resolve_identity(self, identity_token):

        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            SELECT id, total_sessions
            FROM identities
            WHERE identity_token = %s
            """,
            (identity_token,)
        )

        identity = cur.fetchone()

        if identity:

            cur.execute(
                """
                UPDATE identities
                SET last_seen = NOW(),
                    total_sessions = total_sessions + 1
                WHERE id = %s
                """,
                (identity["id"],)
            )

            self.conn.commit()

            return identity["id"]

        # create new identity

        cur.execute(
            """
            INSERT INTO identities (identity_token)
            VALUES (%s)
            RETURNING id
            """,
            (identity_token,)
        )

        identity_id = cur.fetchone()["id"]

        self.conn.commit()

        return identity_id

    # ================================
    # Register Session
    # ================================

    def register_session(self, identity_id, session_id):

        cur = self.conn.cursor()

        cur.execute(
            """
            INSERT INTO sessions (identity_id, session_id)
            VALUES (%s, %s)
            ON CONFLICT (session_id) DO NOTHING
            """,
            (identity_id, session_id)
        )

        self.conn.commit()