import os

import chromadb
from chromadb.config import Settings
from openai import OpenAI

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "curionest")


class ChromaRAGStore:
    def __init__(self):
        self.client = OpenAI()
        self.chroma = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma.get_or_create_collection(name=COLLECTION_NAME)

    def _normalize(self, text):
        return (text or "").strip().lower()

    def retrieve(self, query, context, k=4):
        chapter = self._normalize(context.get("chapter"))
        subject = self._normalize(context.get("subject"))

        filters = []
        if subject:
            filters.append({"subject": subject})
        if chapter:
            filters.append({"chapter": chapter})

        where = None
        if len(filters) == 1:
            where = filters[0]
        elif len(filters) > 1:
            where = {"$and": filters}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=k,
                where=where,
            )
            docs = (results.get("documents") or [[]])[0]
            metadatas = (results.get("metadatas") or [[]])[0]
            return docs, metadatas
        except Exception:
            return [], []

    def generate(self, query, docs):
        context_text = "\n\n".join(docs)
        prompt = f"""
You are CurioNest, a warm school tutor.

Follow all rules strictly:
- Use only the given context.
- Keep answer to 2-3 short lines.
- Use simple student-friendly words.
- Add one tiny example.
- If context is not enough, reply exactly: "I need the correct chapter context to answer this safely."
- Do not invent facts.
- If math appears, format with KaTeX delimiters like \\(a^2+b^2\\) or $$x=2$$.

CONTEXT:
{context_text}

QUESTION:
{query}
"""
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception:
            return None

    def query(self, question, context):
        docs, _ = self.retrieve(question, context)
        if not docs:
            return None

        answer = self.generate(question, docs)
        if not answer:
            return None
        if "I need the correct chapter context to answer this safely." in answer:
            return None

        return answer
