import os
import re
import json
import logging
from typing import Dict
from openai import OpenAI

from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService
from engine.economics_engine import EscalationEconomicsEngine


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CLASSIFICATION_MAX_TOKENS = int(os.getenv("CLASSIFICATION_MAX_TOKENS", "120"))
EXPLAIN_MAX_TOKENS = int(os.getenv("EXPLAIN_MAX_TOKENS", "1200"))


def normalize_latex(text: str):

    if not text:
        return text

    text = re.sub(r"\\\((.*?)\\\)", r"\\[\1\\]", text)
    text = re.sub(r"(?:\b[a-zA-Z]\n){3,}", "", text)

    return text.strip()


def safe_json_parse(response_content: str, default: Dict):

    try:

        cleaned = re.sub(r"^```json\s*", "", response_content.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        return json.loads(cleaned)

    except Exception:

        logging.error("JSON parse failure")
        return default


class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine=None):

        self.rag_store = rag_store
        self.session_engine = session_engine

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        self.client = OpenAI(api_key=api_key)

        self.logger = LoggingService()
        self.lead_persistence = LeadPersistenceService()
        self.economics_engine = EscalationEconomicsEngine()

    # =====================================================
    # ENTRY POINT
    # =====================================================

    def receive_question(self, question: str, context: Dict[str, str], session_id="default"):

        subject = context.get("subject")
        chapter = context.get("chapter")

        classification = self.classify_question(question)

        intent = classification["intent"]
        difficulty = classification["difficulty"]
        confidence = classification["confidence"]

        # AI signal detection (NO hardcoding)
        signals = self.extract_learning_signals(question)

        try:

            chunks = self.rag_store.search(question, subject, chapter)

        except Exception as e:

            self.logger.log("RAG_ERROR", str(e))
            chunks = []

        coverage = len(chunks)

        decision = self.compute_escalation(
            intent,
            difficulty,
            confidence,
            signals,
            coverage
        )

        if decision == "ESCALATE":

            return self.escalate(
                question,
                subject,
                chapter,
                signals.get("summary", "Student likely needs teacher assistance"),
                "ESC_LEARNING_SUPPORT",
                session_id,
                confidence
            )

        if coverage > 0:

            return self.explain_with_ai(question, chunks)

        self.logger.log("RAG_FALLBACK", {"question": question})

        return self.explain_without_context(question)

    # =====================================================
    # AI CLASSIFIER
    # =====================================================

    def classify_question(self, question: str):

        prompt = f"""
Analyze the student question.

Return JSON only.

intent:
["CONCEPT_LEARNING","CONFUSION","HELP_REQUEST","ADVANCED_TOPIC","GENERAL"]

difficulty:
["BASIC","INTERMEDIATE","ADVANCED"]

confidence: 0.0-1.0

Question:
{question}
"""

        default = {
            "intent": "CONCEPT_LEARNING",
            "difficulty": "BASIC",
            "confidence": 0.5
        }

        try:

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=CLASSIFICATION_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": prompt}
                ]
            )

            data = safe_json_parse(response.choices[0].message.content, default)

            intent = data.get("intent", default["intent"])
            difficulty = data.get("difficulty", default["difficulty"])

            if isinstance(intent, list):
                intent = intent[0]

            if isinstance(difficulty, list):
                difficulty = difficulty[0]

            return {
                "intent": intent,
                "difficulty": difficulty,
                "confidence": float(data.get("confidence", 0.5))
            }

        except Exception:

            return default

    # =====================================================
    # AI SIGNAL DETECTION (NO HARDCODING)
    # =====================================================

    def extract_learning_signals(self, question: str):

        prompt = f"""
Analyze the student message and detect learning signals.

Return JSON only.

signals:
["CONFUSION","URGENCY","HELP_SEEKING","ADVANCED_TOPIC","NONE"]

signal_strength: 0-10

summary: short explanation

Student message:
{question}
"""

        default = {
            "signals": ["NONE"],
            "signal_strength": 1,
            "summary": "normal learning request"
        }

        try:

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=120,
                messages=[
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": prompt}
                ]
            )

            data = safe_json_parse(response.choices[0].message.content, default)

            signals = data.get("signals", ["NONE"])

            if isinstance(signals, str):
                signals = [signals]

            return {
                "signals": signals,
                "strength": int(data.get("signal_strength", 1)),
                "summary": data.get("summary", "")
            }

        except Exception:

            return default

    # =====================================================
    # ESCALATION DECISION
    # =====================================================

    def compute_escalation(self, intent, difficulty, confidence, signals, coverage):

        score = 0

        # AI derived signal strength
        score += signals.get("strength", 1)

        # coverage weakness increases escalation chance
        if coverage < 2:
            score += 3

        self.logger.log("ESCALATION_SIGNAL_SCORE", {
            "score": score,
            "signals": signals
        })

        if score >= 8:
            return "ESCALATE"

        return "RESPOND"

    # =====================================================
    # RAG ANSWER
    # =====================================================

    def explain_with_ai(self, question, chunks):

        content = "\n\n".join(chunks)

        prompt = f"""
Use ONLY the syllabus context.

Context:
{content}

Question:
{question}

Answer format:

1. Concept
2. Formula
3. Example
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=EXPLAIN_MAX_TOKENS,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You are an academic tutor."},
                {"role": "user", "content": prompt}
            ]
        )

        return {
            "type": "answer",
            "message": normalize_latex(res.choices[0].message.content.strip())
        }

    # =====================================================
    # FALLBACK ANSWER
    # =====================================================

    def explain_without_context(self, question):

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=EXPLAIN_MAX_TOKENS,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You are a helpful tutor."},
                {"role": "user", "content": question}
            ]
        )

        return {
            "type": "answer",
            "message": normalize_latex(res.choices[0].message.content.strip())
        }

    # =====================================================
    # ESCALATION
    # =====================================================

    def escalate(self, question, subject, chapter, reason, code, session_id, confidence):

        self.lead_persistence.upsert_lead(
            session_id=session_id,
            subject=subject,
            chapter=chapter,
            question=question,
            escalation_code=code,
            escalation_reason=reason,
            confidence=confidence,
            engagement_score=0,
            intent_strength=confidence,
            status="NEW"
        )

        return {
            "type": "escalation",
            "message": "A teacher can help you with this question.",
            "escalation_code": code,
            "escalation_reason": reason
        }