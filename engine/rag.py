import os
import json

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

    def classify_intent(self, question, context, attempts=1):
        prompt = f"""
You are an intent classifier for CurioNest (education tutor + lead generation).
Return strict JSON only with keys:
- intent: one of [learning, confusion, frustration, help, greeting, exam_support, off_topic]
- confidence: float 0 to 1
- needs_teacher: true/false
- reason: short string

Rules:
- Prioritize teach-first.
- For simple concept queries ("what is", "how does", "define"), set intent=learning and needs_teacher=false.
- First query can come from student/parent/teacher; always keep it conversational and helpful.
- If question asks for teacher directly, set intent=help and needs_teacher=true.
- If user asks concept + teacher together, set intent=learning and needs_teacher=true.
- For random/non-syllabus questions, set off_topic and needs_teacher=true only when advanced/urgent.
- attempts={attempts}: if attempts >=3 and confusion present, needs_teacher=true.

Board={context.get("board","")}
Subject={context.get("subject","")}
Chapter={context.get("chapter","")}
Question={question}
"""
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = (response.choices[0].message.content or "").strip()
            data = json.loads(raw)
            return {
                "intent": (data.get("intent") or "learning").lower(),
                "confidence": float(data.get("confidence", 0.6)),
                "needs_teacher": bool(data.get("needs_teacher", False)),
                "reason": (data.get("reason") or "model_inference")[:120],
            }
        except Exception:
            return {
                "intent": "learning",
                "confidence": 0.5,
                "needs_teacher": False,
                "reason": "fallback_classifier",
            }

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
