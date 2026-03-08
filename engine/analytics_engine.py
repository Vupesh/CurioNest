import os
import psycopg2


class AnalyticsEngine:

    def __init__(self):

        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )

    # ============================================
    # TOTAL LEADS
    # ============================================

    def total_leads(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) FROM leads
            """
        )

        result = cursor.fetchone()[0]

        cursor.close()

        return result

    # ============================================
    # ESCALATION DISTRIBUTION
    # ============================================

    def escalation_distribution(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT event_code, COUNT(*)
            FROM lead_events
            GROUP BY event_code
            ORDER BY COUNT(*) DESC
            """
        )

        rows = cursor.fetchall()

        cursor.close()

        return rows

    # ============================================
    # LEAD QUALITY DISTRIBUTION
    # ============================================

    def lead_quality_distribution(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT
                CASE
                    WHEN confidence >= 80 THEN 'HIGH'
                    WHEN confidence >= 50 THEN 'MEDIUM'
                    ELSE 'LOW'
                END AS quality,
                COUNT(*)
            FROM leads
            GROUP BY quality
            ORDER BY quality
            """
        )

        rows = cursor.fetchall()

        cursor.close()

        return rows

    # ============================================
    # TOP SUBJECT DEMAND
    # ============================================

    def subject_demand(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT subject, COUNT(*)
            FROM leads
            GROUP BY subject
            ORDER BY COUNT(*) DESC
            """
        )

        rows = cursor.fetchall()

        cursor.close()

        return rows

    # ============================================
    # TOP CHAPTER DEMAND
    # ============================================

    def chapter_demand(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT chapter, COUNT(*)
            FROM leads
            GROUP BY chapter
            ORDER BY COUNT(*) DESC
            """
        )

        rows = cursor.fetchall()

        cursor.close()

        return rows

    # ============================================
    # ESCALATION TIMELINE
    # ============================================

    def escalation_timeline(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT DATE(created_at), COUNT(*)
            FROM lead_events
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
            """
        )

        rows = cursor.fetchall()

        cursor.close()

        return rows