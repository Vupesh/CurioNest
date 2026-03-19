import os
import re
import json
from typing import Dict, Any, List

from openai import OpenAI
from services.logging_service import LoggingService
from engine.cache_engine import CacheEngine
from engine.lead_persistence import LeadPersistenceService


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def normalize_latex(text: str) -> str:
    if not text:
        return text

    # Fix broken brackets
    text = text.replace("\\", "\\\\")
    text = text.replace("$$$$", "$$")

    # Convert [ ... ] → $$ ... $$
    text = re.sub(r"\[\s*(.*?)\s*\]", r"$$\1$$", text)

    # Remove broken trailing slashes
    text = re.sub(r"\\\s*$", "", text)

    return text.strip()


class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine=None):

        self.rag_store = rag_store
        self.session_engine = session_engine

        self.cache = CacheEngine()
        self.logger = LoggingService()
        self.lead_persistence = LeadPersistenceService()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        self.client = OpenAI(api_key=api_key)

        # ✅ FIX: session-based tracking
        self.session_confusion = {}
        self.session_escalated = {}

    # =====================================================
    # MAIN ENTRY
    # =====================================================

    def receive_question(self, question: str, context: Dict[str, str], session_id: str):

        try:

            question = question.strip()

            subject = context.get("subject")
            chapter = context.get("chapter")

            # ---------- CACHE ----------

            cached = self.cache.lookup(question, subject, chapter)

            if cached:
                print("CACHE_HIT")
                return {"type": "answer", "message": cached}

            # ---------- SESSION MEMORY ----------

            if self.session_engine:
                self.session_engine.store_message(session_id, "user", question)

            # ---------- INTENT ----------

            intent = self._detect_intent(question)

            # ---------- NUMERICAL FIX ----------

            is_numerical = bool(re.search(r"\d", question))

            # ---------- RAG ----------

            try:
                chunks = self.rag_store.search(question, subject, chapter)
            except:
                chunks = []

            coverage = len(chunks)

            # =====================================================
            # ESCALATION FIX (FINAL LOGIC)
            # =====================================================

            if not self.session_escalated.get(session_id, False):

                count = self.session_confusion.get(session_id, 0)

                if intent in ["CONFUSION", "HELP_REQUEST"]:
                    count += 1
                    self.session_confusion[session_id] = count

                # ❗ NEVER escalate numericals
                if is_numerical:
                    pass

                else:

                    # escalate only after repeated confusion
                    if count >= 3:
                        self.session_escalated[session_id] = True
                        return self._escalate(question, subject, chapter, session_id)

                    # explicit help request
                    if "teacher" in question.lower():
                        self.session_escalated[session_id] = True
                        return self._escalate(question, subject, chapter, session_id)

            # =====================================================
            # ANSWER (NO SUBJECT BLOCKING)
            # =====================================================

            if coverage > 0:
                answer = self._answer_with_context(question, chunks)
            else:
                answer = self._answer_general(question)

            answer = normalize_latex(answer)

            # ---------- CACHE STORE ----------

            self.cache.store(question, subject, chapter, answer)

            # ---------- SAVE MEMORY ----------

            if self.session_engine:
                self.session_engine.store_message(session_id, "assistant", answer)

            return {"type": "answer", "message": answer}

        except Exception as e:

            print("AGENT ERROR:", e)

            return {
                "type": "error",
                "message": "System temporarily unavailable."
            }

    # =====================================================
    # INTENT DETECTION (LIGHTWEIGHT)
    # =====================================================

    def _detect_intent(self, question: str):

        q = question.lower()

        if any(word in q for word in ["confused", "not understand", "dont understand"]):
            return "CONFUSION"

        if any(word in q for word in ["help", "teacher", "doubt"]):
            return "HELP_REQUEST"

        return "CONCEPT_LEARNING"

    # =====================================================
    # ANSWERS
    # =====================================================

    def _answer_with_context(self, question, chunks):

        context = "\n\n".join(chunks)

        prompt = f"""
Use this syllabus context:

{context}

Answer clearly for a student:

{question}
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return res.choices[0].message.content

    def _answer_general(self, question):

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            max_tokens=1000,
            messages=[{"role": "user", "content": question}]
        )

        return res.choices[0].message.content

    # =====================================================
    # ESCALATION
    # =====================================================

    def _escalate(self, question, subject, chapter, session_id):

        try:

            self.lead_persistence.upsert_lead(
                session_id=session_id,
                subject=subject,
                chapter=chapter,
                question=question,
                escalation_code="ESC_LEARNING_SUPPORT",
                escalation_reason="student_needs_help",
                confidence=0.8,
                engagement_score=0,
                intent_strength=0.8,
                status="NEW"
            )

        except Exception as e:
            print("LEAD ERROR:", e)

        return {
            "type": "escalation",
            "message": "A teacher will contact you shortly."
        }
    