import os
import psycopg2
from services.logging_service import LoggingService


class DomainEngine:

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

            self.logger.log("DOMAIN_DB_CONNECTION_ERROR", str(e))
            self.conn = None


    # =====================================
    # RESOLVE DOMAIN
    # =====================================

    def resolve_domain(self, data):

        domain = data.get("domain")

        if not domain:
            return "education"

        return domain


    # =====================================
    # BUILD CONTEXT
    # =====================================

    def build_context(self, domain, data):

        context = {
            "domain": domain,
            "board": data.get("board"),
            "subject": data.get("subject"),
            "chapter": data.get("chapter"),
        }

        return context


    # =====================================
    # FETCH DOMAIN CONFIGURATION
    # =====================================

    def get_domain_config(self):

        if not self.conn:
            return {}

        try:

            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT
                    d.name as domain,
                    b.name as board,
                    c.name as category,
                    t.name as topic
                FROM domains d
                JOIN boards b ON b.domain_id = d.id
                JOIN categories c ON c.board_id = b.id
                JOIN topics t ON t.category_id = c.id
                ORDER BY d.name, b.name, c.name
            """)

            rows = cursor.fetchall()

            cursor.close()

            config = {}

            for domain, board, category, topic in rows:

                config.setdefault(domain, {})
                config[domain].setdefault(board, {})
                config[domain][board].setdefault(category, [])

                config[domain][board][category].append(topic)

            return config

        except Exception as e:

            self.logger.log("DOMAIN_CONFIG_FETCH_ERROR", str(e))
            return {}
        