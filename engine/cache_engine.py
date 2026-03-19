import os
import psycopg2
import numpy as np
import json
from langchain_openai import OpenAIEmbeddings

SIMILARITY_THRESHOLD = 0.85
CACHE_SCAN_LIMIT = 200


class CacheEngine:

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise RuntimeError("DATABASE_URL not configured")

        self.embedder = OpenAIEmbeddings(model="text-embedding-3-small")

    def _connect(self):
        return psycopg2.connect(self.database_url)

    def cosine_similarity(self, a, b):
        a = np.array(a)
        b = np.array(b)
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def lookup(self, question, subject=None, chapter=None):

        try:
            query_embedding = self.embedder.embed_query(question)

            conn = self._connect()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT embedding, answer
                FROM qa_cache
                WHERE subject = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (subject, CACHE_SCAN_LIMIT)
            )

            rows = cur.fetchall()
            cur.close()
            conn.close()

        except Exception:
            return None

        best_score = 0
        best_answer = None

        for embedding, answer in rows:
            try:
                if isinstance(embedding, str):
                    embedding = json.loads(embedding)

                score = self.cosine_similarity(query_embedding, embedding)

                if score > SIMILARITY_THRESHOLD and score > best_score:
                    best_score = score
                    best_answer = answer

            except Exception:
                continue

        return best_answer

    def store(self, question, subject, chapter, answer):

        try:
            embedding = self.embedder.embed_query(question)

            conn = self._connect()
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO qa_cache
                (question, embedding, answer, subject, chapter)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    question,
                    json.dumps(embedding),
                    answer,
                    subject,
                    chapter
                )
            )

            conn.commit()
            cur.close()
            conn.close()

        except Exception:
            pass