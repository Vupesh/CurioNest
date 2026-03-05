import os
import psycopg2
from psycopg2.extras import RealDictCursor


class AnalyticsEngine:

    def __init__(self):

        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )

    # --------------------------------------------------
    # 1. Escalation Signal Distribution
    # --------------------------------------------------

    def get_escalation_summary(self):

        query = """
        SELECT event_code, COUNT(*) AS total
        FROM lead_events
        GROUP BY event_code
        ORDER BY total DESC
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()

    # --------------------------------------------------
    # 2. Teacher Demand Heatmap
    # --------------------------------------------------

    def get_teacher_demand(self):

        query = """
        SELECT subject, chapter, COUNT(*) AS demand
        FROM leads
        GROUP BY subject, chapter
        ORDER BY demand DESC
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()

    # --------------------------------------------------
    # 3. Lead Funnel Distribution
    # --------------------------------------------------

    def get_lead_distribution(self):

        query = """
        SELECT status, COUNT(*) AS total
        FROM leads
        GROUP BY status
        ORDER BY total DESC
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()

    # --------------------------------------------------
    # 4. Escalation Timeline
    # --------------------------------------------------

    def get_escalation_trend(self):

        query = """
        SELECT DATE(created_at) AS day, COUNT(*) AS total
        FROM leads
        GROUP BY day
        ORDER BY day ASC
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()

    # --------------------------------------------------
    # 5. Engagement Intelligence
    # --------------------------------------------------

    def get_engagement_metrics(self):

        query = """
        SELECT
            AVG(engagement_score) AS avg_engagement,
            MAX(engagement_score) AS max_engagement,
            MIN(engagement_score) AS min_engagement
        FROM leads
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchone()

    # --------------------------------------------------
    # Health check
    # --------------------------------------------------

    def get_total_leads(self):

        query = "SELECT COUNT(*) FROM leads"

        with self.conn.cursor() as cur:
            cur.execute(query)
            result = cur.fetchone()
            return result[0]