import os
import re
import json
import logging
from typing import Dict, Any, List

from openai import OpenAI

from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService
from engine.economics_engine import EscalationEconomicsEngine


# ==================== CONFIGURATION ====================

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CLASSIFICATION_MAX_TOKENS = int(os.getenv("CLASSIFICATION_MAX_TOKENS", "160"))
EXPLAIN_MAX_TOKENS = int(os.getenv("EXPLAIN_MAX_TOKENS", "1200"))

ESCALATION_THRESHOLD = int(os.getenv("ESCALATION_THRESHOLD", "10"))
MIN_COVERAGE = int(os.getenv("MIN_COVERAGE", "2"))
CONTEXT_WEAK_PENALTY = int(os.getenv("CONTEXT_WEAK_PENALTY", "2"))
COVERAGE_PENALTY = int(os.getenv("COVERAGE_PENALTY", "2"))


def normalize_latex(text: str) -> str:

    if not text:
        return text

    text = re.sub(r"\\\((.*?)\\\)", r"\\[\1\\]", text)
    text = re.sub(r"(?:\b[a-zA-Z]\n){3,}", "", text)

    return text.strip()


def safe_json_parse(response_content: str, default: Dict) -> Dict:

    try:
        cleaned = re.sub(r"^```json\s*", "", response_content.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)

    except Exception:
        logging.error("JSON parse failure", exc_info=True)
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

    def receive_question(self, question: str, context: Dict[str, str], session_id: str = "default") -> Dict[str, Any]:

        subject = context.get("subject")
        chapter = context.get("chapter")

        # ---------------------------
        # SESSION MEMORY STORE
        # ---------------------------

        if self.session_engine:
            self.session_engine.store_message(session_id, "user", question)

        conversation_history = []

        if self.session_engine:
            conversation_history = self.session_engine.get_recent_messages(session_id)

        history_text = "\n".join(
            [f'{m["role"]}: {m["message"]}' for m in conversation_history]
        )

        # ---------------------------
        # ANALYZE QUESTION
        # ---------------------------

        analysis = self.analyze_question(question, history_text)

        intent = analysis["intent"]
        difficulty = analysis["difficulty"]
        confidence = analysis["confidence"]
        signals = analysis["signals"]

        # ---------------------------
        # RAG RETRIEVAL
        # ---------------------------

        try:
            chunks = self.rag_store.search(question, subject, chapter)
        except Exception as e:
            self.logger.log("RAG_ERROR", str(e))
            chunks = []

        coverage = len(chunks)

        context_quality = "PARTIAL"

        if coverage >= MIN_COVERAGE:
            context_quality = self.evaluate_context_quality(question, chunks)

        decision = self.compute_escalation(
            intent,
            difficulty,
            confidence,
            signals,
            coverage,
            context_quality
        )

        if decision == "ESCALATE":

            return self.escalate(
                question,
                subject,
                chapter,
                signals.get("summary", "Student likely needs expert assistance"),
                "ESC_LEARNING_SUPPORT",
                session_id,
                confidence
            )

        if coverage > 0:

            response = self.explain_with_ai(question, chunks, history_text)

        else:

            self.logger.log("RAG_FALLBACK", {"question": question})

            response = self.explain_without_context(question, history_text)

        # ---------------------------
        # STORE AI RESPONSE
        # ---------------------------

        if self.session_engine:
            self.session_engine.store_message(session_id, "ai", response["message"])

        return response

    # =====================================================
    # COMBINED ANALYSIS
    # =====================================================

    def analyze_question(self, question: str, history_text: str) -> Dict[str, Any]:

        prompt = f"""
Conversation History:
{history_text}

Analyze the student question.

Return JSON only.

intent:
["CONCEPT_LEARNING","CONFUSION","HELP_REQUEST","ADVANCED_TOPIC","GENERAL"]

difficulty:
["BASIC","INTERMEDIATE","ADVANCED"]

confidence: 0.0-1.0

signals:
["CONFUSION","URGENCY","HELP_SEEKING","ADVANCED_TOPIC","NONE"]

signal_strength: 0-10

summary: short explanation

Question:
{question}
"""

        default = {
            "intent": "CONCEPT_LEARNING",
            "difficulty": "BASIC",
            "confidence": 0.5,
            "signals": ["NONE"],
            "signal_strength": 1,
            "summary": "normal learning request"
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

            signals = data.get("signals", ["NONE"])

            if isinstance(signals, str):
                signals = [signals]

            return {
                "intent": data.get("intent", default["intent"]),
                "difficulty": data.get("difficulty", default["difficulty"]),
                "confidence": float(data.get("confidence", default["confidence"])),
                "signals": {
                    "signals": signals,
                    "strength": int(data.get("signal_strength", default["signal_strength"])),
                    "summary": data.get("summary", default["summary"])
                }
            }

        except Exception:

            return {
                "intent": default["intent"],
                "difficulty": default["difficulty"],
                "confidence": default["confidence"],
                "signals": {
                    "signals": default["signals"],
                    "strength": default["signal_strength"],
                    "summary": default["summary"]
                }
            }

    # =====================================================
    # CONTEXT QUALITY
    # =====================================================

    def evaluate_context_quality(self, question: str, chunks: List[str]) -> str:

        content = "\n\n".join(chunks[:3])

        prompt = f"""
Determine if the syllabus context is sufficient to answer the student's question.

Return JSON only.

quality:
["STRONG","PARTIAL","WEAK"]

Question:
{question}

Context:
{content}
"""

        default = {"quality": "PARTIAL"}

        try:

            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=80,
                messages=[
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": prompt}
                ]
            )

            data = safe_json_parse(res.choices[0].message.content, default)

            return data.get("quality", "PARTIAL")

        except Exception:
            return "PARTIAL"

    # =====================================================
    # ESCALATION DECISION
    # =====================================================

    def compute_escalation(self, intent, difficulty, confidence, signals, coverage, context_quality):

        score = signals.get("strength", 1)

        if coverage < MIN_COVERAGE:
            score += COVERAGE_PENALTY

        if context_quality == "WEAK":
            score += CONTEXT_WEAK_PENALTY

        self.logger.log("ESCALATION_SIGNAL_SCORE", {
            "score": score,
            "threshold": ESCALATION_THRESHOLD,
            "intent": intent,
            "difficulty": difficulty,
            "confidence": confidence,
            "coverage": coverage,
            "context_quality": context_quality,
            "signals": signals
        })

        return "ESCALATE" if score >= ESCALATION_THRESHOLD else "RESPOND"

    # =====================================================
    # RAG ANSWER
    # =====================================================

    def explain_with_ai(self, question: str, chunks: List[str], history_text: str):

        content = "\n\n".join(chunks)

        prompt = f"""
Conversation History:
{history_text}

Use ONLY the syllabus context.

Context:
{content}

Question:
{question}

Answer format:

Concept
Formula
Example
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
    # FALLBACK
    # =====================================================

    def explain_without_context(self, question: str, history_text: str):

        prompt = f"""
Conversation History:
{history_text}

Question:
{question}
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=EXPLAIN_MAX_TOKENS,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You are a helpful tutor."},
                {"role": "user", "content": prompt}
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