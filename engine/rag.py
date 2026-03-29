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

    # ✅ MULTI-STAGE RETRIEVAL (UNCHANGED)
    def retrieve(self, query, context, k=4):
        chapter = self._normalize(context.get("chapter"))
        subject = self._normalize(context.get("subject"))

        try:
            if subject and chapter:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=k,
                    where={"$and": [{"subject": subject}, {"chapter": chapter}]}
                )
                docs = (results.get("documents") or [[]])[0]
                if docs:
                    return docs, []

            if subject:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=k,
                    where={"subject": subject}
                )
                docs = (results.get("documents") or [[]])[0]
                if docs:
                    return docs, []

            results = self.collection.query(
                query_texts=[query],
                n_results=k
            )
            docs = (results.get("documents") or [[]])[0]

            return docs, []

        except Exception:
            return [], []

    # ✅ GENERATION (UNCHANGED)
    def generate(self, query, docs):
        context_text = "\n\n".join(docs) if docs else ""

        prompt = f"""
You are CurioNest, a friendly school tutor.

Rules:
- Use given context if available.
- If context is weak, still explain the basic idea safely.
- Keep answer 2-3 short lines.
- Use simple student-friendly language.
- Add one small real-life example.
- Do NOT say you don't have context.
- Do NOT refuse to answer.

CONTEXT:
{context_text}

QUESTION:
{query}
"""

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception:
            return None

    # 🔥 UPDATED CLASSIFIER (THIS IS THE FIX)
    def classify_intent(self, question, context, attempts=1):
        prompt = f"""
You are a smart academic assistant for CurioNest.

Your job is to analyze a student's question and decide:
1. What is the intent?
2. Does this student likely need a teacher?

Think like a real teacher:
"Can an average Class X student understand this on their own?"

---

Return ONLY JSON with keys:
- intent: one of [learning, confusion, frustration, help, greeting, exam_support, off_topic]
- confidence: float (0 to 1)
- needs_teacher: true/false
- reason: short explanation

---

Guidelines:

- Simple definition or basic concept → needs_teacher = false
- Repeated confusion → may need teacher
- Direct request for teacher → needs_teacher = true
- Emotional stress → needs_teacher = true

🔥 VERY IMPORTANT:

Set needs_teacher = true if:
- Question requires deep thinking or reasoning
- Multiple concepts are combined
- It feels advanced for Class X level
- Requires step-by-step explanation
- Student may struggle even after short answer

Even if you CAN answer it, still mark TRUE if it's difficult.

---

Context:
Board: {context.get("board","")}
Subject: {context.get("subject","")}
Chapter: {context.get("chapter","")}

Question:
{question}

Attempts:
{attempts}

Return JSON only.
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

    # ✅ QUERY (UNCHANGED)
    def query(self, question, context):
        docs, _ = self.retrieve(question, context)

        answer = self.generate(question, docs)

        if not answer or len(answer.strip()) < 15:
            return (
                "Let me explain simply: This is a basic concept from your subject. "
                "Think of it step by step with a small real-life example."
            )

        return answer