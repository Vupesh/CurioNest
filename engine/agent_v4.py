import os
import json
import re
import time
from typing import Dict, Any, List, Tuple
from datetime import datetime

from openai import OpenAI, APIError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from services.logging_service import LoggingService
from engine.cache_engine import CacheEngine
from engine.query_guardrail import QueryGuardrail
from engine.lead_persistence import LeadPersistenceService
from engine.economics_engine import EscalationEconomicsEngine



# ================= CONFIG =================

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

CLASSIFICATION_MAX_TOKENS = int(os.getenv("CLASSIFICATION_MAX_TOKENS", "150"))
ANSWER_MAX_TOKENS = int(os.getenv("ANSWER_MAX_TOKENS", "1000"))

ESCALATION_THRESHOLD = int(os.getenv("ESCALATION_THRESHOLD", "12"))
MAX_QUESTION_LENGTH = int(os.getenv("MAX_QUESTION_LENGTH", "500"))


# ================= LATEX FIX =================

def normalize_latex(text: str) -> str:
    if not text:
        return text

    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text)
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text)

    text = re.sub(r"\n\s*\n", "\n\n", text)

    return text.strip()


# ================= JSON SAFE PARSE =================

def safe_json_parse(content: str, default: Dict) -> Dict:
    try:
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", content.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)
    except Exception:
        return default


# ==========================================================
# AGENT
# ==========================================================

class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine=None):

        self.rag_store = rag_store
        self.session_engine = session_engine

        self.logger = LoggingService()
        self.cache = CacheEngine()
        self.guardrail = QueryGuardrail()
        self.lead_persistence = LeadPersistenceService()
        self.economics_engine = EscalationEconomicsEngine()
        

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        self.client = OpenAI(api_key=api_key)

        self.start_time = datetime.now()

    # =====================================================
    # MAIN ENTRY
    # =====================================================

    def receive_question(self, question: str, context: Dict[str, str], session_id: str):

        try:

            # ---------- VALIDATION ----------

            if not question or not question.strip():
                return {"type": "error", "message": "Please enter a valid question."}

            if len(question) > MAX_QUESTION_LENGTH:
                question = question[:MAX_QUESTION_LENGTH]

            subject = context.get("subject")
            chapter = context.get("chapter")

            if not subject or not chapter:
                return {"type": "error", "message": "Please select subject and chapter."}

            # ---------- GUARDRAIL ----------

            guard = self.guardrail.check(question)

            if guard:
                return {
                    "type": "answer",
                    "message": guard.get("message", "Please ask an academic question.")
                }

            # ---------- CACHE CHECK ----------

            try:
                cached_answer = self.cache.search_cache(question, subject)

                if cached_answer:
                    self.logger.log("CACHE_HIT", question[:80])
                    return {
                        "type": "answer",
                        "message": cached_answer
                    }

            except Exception as e:
                self.logger.log("CACHE_ERROR", str(e))

            # ---------- HISTORY ----------

            history = []
            if self.session_engine:
                history = self.session_engine.get_recent_messages(session_id)

            if self.session_engine:
                self.session_engine.store_message(session_id, "user", question)

            # ---------- ANALYSIS ----------

            analysis = self._analyze_question(question)

            intent = analysis["intent"]
            difficulty = analysis["difficulty"]
            confidence = analysis["confidence"]

            # ---------- RAG ----------

            try:
                chunks = self.rag_store.search(question, subject, chapter)
            except Exception:
                chunks = []

            coverage = len(chunks)

            # ---------- ESCALATION ----------

            if self._should_escalate(intent, difficulty, coverage):

                return self._escalate(
                    question, subject, chapter, session_id, confidence, intent
                )

            # ---------- ANSWER ----------

            if coverage > 0:
                answer = self._answer_with_context(question, chunks, history)
            else:
                answer = self._answer_general(question, history)

            answer = normalize_latex(answer)

            # ---------- CACHE STORE ----------

            try:
                self.cache.store_cache(question, answer, subject, chapter)
            except Exception as e:
                self.logger.log("CACHE_STORE_ERROR", str(e))

            # ---------- STORE HISTORY ----------

            if self.session_engine:
                self.session_engine.store_message(session_id, "assistant", answer)

            return {
                "type": "answer",
                "message": answer
            }

        except Exception as e:

            self.logger.log("FATAL_ERROR", str(e))

            return {
                "type": "error",
                "message": "System temporarily unavailable."
            }

    # =====================================================
    # ANALYSIS
    # =====================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=5),
        retry=retry_if_exception_type((APIError, RateLimitError))
    )
    def _analyze_question(self, question: str):

        prompt = f"""
Classify the question.

Return JSON:

intent: CONCEPT_LEARNING | CONFUSION | HELP_REQUEST | ADVANCED_TOPIC | GENERAL
difficulty: BASIC | INTERMEDIATE | ADVANCED
confidence: 0-1

Question: {question}
"""

        default = {
            "intent": "CONCEPT_LEARNING",
            "difficulty": "BASIC",
            "confidence": 0.7
        }

        try:
            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=CLASSIFICATION_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": "Return JSON only"},
                    {"role": "user", "content": prompt}
                ]
            )

            return safe_json_parse(res.choices[0].message.content, default)

        except Exception:
            return default

    # =====================================================
    # ESCALATION
    # =====================================================

    def _should_escalate(self, intent, difficulty, coverage):

        score = 0

        if intent == "HELP_REQUEST":
            score += 10
        if intent == "CONFUSION":
            score += 8
        if intent == "ADVANCED_TOPIC":
            score += 6

        if difficulty == "ADVANCED":
            score += 4

        if coverage == 0:
            score += 5

        return score >= ESCALATION_THRESHOLD

    # =====================================================
    # ANSWERS
    # =====================================================

    def _answer_with_context(self, question, chunks, history):

        context = "\n\n".join(chunks)

        prompt = f"""
Use syllabus context.

{context}

Question:
{question}

Explain clearly for exams.
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=ANSWER_MAX_TOKENS,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )

        return res.choices[0].message.content

    def _answer_general(self, question, history):

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=ANSWER_MAX_TOKENS,
            temperature=0.3,
            messages=[{"role": "user", "content": question}]
        )

        return res.choices[0].message.content

    # =====================================================
    # ESCALATE
    # =====================================================

    def _escalate(self, question, subject, chapter, session_id, confidence, intent):

        try:
            self.lead_persistence.upsert_lead(
                session_id=session_id,
                subject=subject,
                chapter=chapter,
                question=question,
                escalation_code="ESC_LEARNING_SUPPORT",
                escalation_reason=intent,
                confidence=confidence,
                engagement_score=0,
                intent_strength=confidence,
                status="NEW"
            )
        except Exception as e:
            self.logger.log("LEAD_ERROR", str(e))

        return {
            "type": "escalation",
            "message": "A teacher will contact you shortly."
        }