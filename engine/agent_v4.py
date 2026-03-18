import os
import re
import json
import logging
from typing import Dict, Any, List

from openai import OpenAI

from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService
from engine.economics_engine import EscalationEconomicsEngine
from engine.cache_engine import CacheEngine


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

CLASSIFICATION_MAX_TOKENS = int(os.getenv("CLASSIFICATION_MAX_TOKENS", "160"))
EXPLAIN_MAX_TOKENS = int(os.getenv("EXPLAIN_MAX_TOKENS", "1200"))

ESCALATION_THRESHOLD = int(os.getenv("ESCALATION_THRESHOLD", "10"))
MIN_COVERAGE = int(os.getenv("MIN_COVERAGE", "2"))

ESCALATION_COOLDOWN = int(os.getenv("ESCALATION_COOLDOWN", "3"))


def normalize_latex(text: str):

    if not text:
        return text

    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text)
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text)

    return text.strip()


def safe_json_parse(response_content: str, default: Dict):

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

        self.cache = CacheEngine()

        self.session_escalations = {}

    # =====================================================
    # ENTRY POINT
    # =====================================================

    def receive_question(self, question: str, context: Dict[str, str], session_id="default"):

        subject = context.get("subject")
        chapter = context.get("chapter")

        # -------- CACHE --------

        try:

            cached = self.cache.lookup(question, subject, chapter)

            if cached:

                self.logger.log("CACHE_HIT", question[:80])

                return {
                    "type": "answer",
                    "message": cached
                }

        except Exception as e:

            self.logger.log("CACHE_ERROR", str(e))

        # -------- RAG --------

        try:

            chunks = self.rag_store.search(question, subject, chapter)

        except Exception as e:

            self.logger.log("RAG_ERROR", str(e))
            chunks = []

        coverage = len(chunks)

        # -------- AI ANALYSIS --------

        analysis = self.analyze_question(question)

        intent = analysis["intent"]
        confidence = analysis["confidence"]
        signals = analysis["signals"]

        # -------- NORMAL RESPONSE --------

        if coverage > 0:

            answer = self.explain_with_ai(question, chunks)

            try:
                self.cache.store(question, subject, chapter, answer["message"])
            except Exception:
                pass

            return answer

        # -------- SUBJECT VALIDATION (ONLY IF RAG FAILS) --------

        if not self.is_question_related(question, subject):

            return {
                "type": "answer",
                "message": "This question appears related to another subject. Please change the subject to get the correct explanation."
            }

        # -------- ESCALATION DECISION --------

        decision = self.compute_escalation(
            intent,
            confidence,
            signals,
            coverage,
            session_id
        )

        if decision == "ESCALATE":

            return self.escalate(
                question,
                subject,
                chapter,
                signals.get("summary", "Student needs help"),
                "ESC_LEARNING_SUPPORT",
                session_id,
                confidence
            )

        # -------- FALLBACK AI --------

        answer = self.explain_without_context(question)

        try:
            self.cache.store(question, subject, chapter, answer["message"])
        except Exception:
            pass

        return answer

    # =====================================================
    # SUBJECT VALIDATION
    # =====================================================

    def is_question_related(self, question, subject):

        if len(question.split()) < 3:
            return True

        prompt = f"""
Determine if the question belongs to the subject.

Return JSON only.

subject: {subject}

question:
{question}

Return:

{{"related": true or false}}
"""

        default = {"related": True}

        try:

            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=60,
                messages=[
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": prompt}
                ]
            )

            data = safe_json_parse(res.choices[0].message.content, default)

            return data.get("related", True)

        except Exception:

            return True

    # =====================================================
    # AI QUESTION ANALYSIS
    # =====================================================

    def analyze_question(self, question):

        prompt = f"""
Analyze the student question.

Return JSON only.

intent:
["CONCEPT_LEARNING","CONFUSION","HELP_REQUEST","ADVANCED_TOPIC","GENERAL"]

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
            "confidence": 0.6,
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

            return {
                "intent": data.get("intent", default["intent"]),
                "confidence": float(data.get("confidence", default["confidence"])),
                "signals": {
                    "signals": data.get("signals", default["signals"]),
                    "strength": int(data.get("signal_strength", default["signal_strength"])),
                    "summary": data.get("summary", default["summary"])
                }
            }

        except Exception:

            return default

    # =====================================================
    # ESCALATION
    # =====================================================

    def compute_escalation(self, intent, confidence, signals, coverage, session_id):

        score = signals.get("strength", 1)

        if coverage < MIN_COVERAGE:
            score += 2

        recent = self.session_escalations.get(session_id, 0)

        if recent >= ESCALATION_COOLDOWN:

            self.session_escalations[session_id] = 0

            return "RESPOND"

        if score >= ESCALATION_THRESHOLD:

            self.session_escalations[session_id] = recent + 1

            return "ESCALATE"

        return "RESPOND"

    # =====================================================
    # RAG ANSWER
    # =====================================================

    def explain_with_ai(self, question, chunks):

        content = "\n\n".join(chunks)

        prompt = f"""
You are a board exam tutor.

Use Markdown.

All equations must use LaTeX.

Inline: $ equation $

Block: $$ equation $$

Structure answer as:

Concept
Equation
Example
Exam Tip

Context:
{content}

Question:
{question}
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
    # ESCALATION EVENT
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