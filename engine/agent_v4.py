import os
import re
import json
import logging
from typing import Dict, Any, List

from openai import OpenAI

from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService
from engine.economics_engine import EscalationEconomicsEngine


# ================= CONFIG =================

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

CLASSIFICATION_MAX_TOKENS = int(os.getenv("CLASSIFICATION_MAX_TOKENS", "160"))
EXPLAIN_MAX_TOKENS = int(os.getenv("EXPLAIN_MAX_TOKENS", "1200"))

ESCALATION_THRESHOLD = int(os.getenv("ESCALATION_THRESHOLD", "10"))
MIN_COVERAGE = int(os.getenv("MIN_COVERAGE", "2"))
CONTEXT_WEAK_PENALTY = int(os.getenv("CONTEXT_WEAK_PENALTY", "2"))
COVERAGE_PENALTY = int(os.getenv("COVERAGE_PENALTY", "2"))

ESCALATION_COOLDOWN = int(os.getenv("ESCALATION_COOLDOWN", "3"))


# ================= UTILITIES =================

def normalize_latex(text: str):
    if not text:
        return text

    # convert \( ... \) → $...$
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text)

    # convert \[ ... \] → $$...$$
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text)

    # convert [ equation ] → $$ equation $$
    text = re.sub(r"\[(.*?)\]", r"$$\1$$", text)

    # fix multi line math
    text = re.sub(r"\n\s*\n", "\n\n", text)

    # remove OCR garbage
    text = re.sub(r"(?:\b[a-zA-Z]\n){3,}", "", text)

    return text.strip()


def safe_json_parse(response_content: str, default: Dict):
    try:
        cleaned = re.sub(
            r"^```json\s*", "", response_content.strip(), flags=re.IGNORECASE
        )

        cleaned = re.sub(r"\s*```$", "", cleaned)

        return json.loads(cleaned)

    except Exception:
        logging.error("JSON parse failure", exc_info=True)
        return default


# ============================================================
# AGENT
# ============================================================

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

        self.session_escalations = {}

    # =====================================================
    # ENTRY POINT
    # =====================================================

    def receive_question(self, question: str, context: Dict[str, str], session_id="default"):
        subject = context.get("subject")
        chapter = context.get("chapter")

        # -------- Subject Guard --------
        subject_check = self.detect_subject_mismatch(question, subject)

        if not subject_check.get("match", True):
            detected = subject_check.get("detected_subject")
            if not detected:
                detected = "another subject"

            return {
                "type": "answer",
                "message": f"This question appears related to {detected}. Please change the subject to get the correct explanation."
            }

        # -------- Analysis --------
        analysis = self.analyze_question(question)

        intent = analysis["intent"]
        difficulty = analysis["difficulty"]
        confidence = analysis["confidence"]
        signals = analysis["signals"]

        # -------- RAG Retrieval --------
        try:
            chunks = self.rag_store.search(question, subject, chapter)
        except Exception as e:
            self.logger.log("RAG_ERROR", str(e))
            chunks = []

        coverage = len(chunks)

        context_quality = "PARTIAL"

        if coverage >= MIN_COVERAGE:
            context_quality = self.evaluate_context_quality(question, chunks)

        # -------- Escalation Decision --------
        decision = self.compute_escalation(
            intent,
            difficulty,
            confidence,
            signals,
            coverage,
            context_quality,
            session_id
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

        # -------- AI Response --------
        if coverage > 0:
            return self.explain_with_ai(question, chunks)

        return self.explain_without_context(question)

    # =====================================================
    # SUBJECT DETECTOR
    # =====================================================

    def detect_subject_mismatch(self, question, subject):
        prompt = f"""
Determine if the question belongs to the subject: {subject}

Return JSON

match: true or false
detected_subject: short subject name

Question:
{question}
"""

        try:
            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=50,
                messages=[
                    {"role": "system", "content": "Return JSON only"},
                    {"role": "user", "content": prompt}
                ]
            )

            data = safe_json_parse(res.choices[0].message.content, {"match": True})

            return data

        except Exception:
            return {"match": True}

    # =====================================================
    # QUESTION ANALYSIS
    # =====================================================

    def analyze_question(self, question: str):
        prompt = f"""
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
                    {"role": "system", "content": "Return JSON only"},
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

    def evaluate_context_quality(self, question: str, chunks: List[str]):
        content = "\n\n".join(chunks[:3])

        prompt = f"""
Determine if the syllabus context is sufficient to answer the student's question.

Return JSON

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
                    {"role": "system", "content": "Return JSON only"},
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

    def compute_escalation(self, intent, difficulty, confidence, signals, coverage, context_quality, session_id):
        if intent in ["CONCEPT_LEARNING", "GENERAL"]:
            return "RESPOND"

        score = signals.get("strength", 1)

        if coverage < MIN_COVERAGE:
            score += COVERAGE_PENALTY

        if context_quality == "WEAK":
            score += CONTEXT_WEAK_PENALTY

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

    def explain_with_ai(self, question: str, chunks: List[str]):
        content = "\n\n".join(chunks)

        prompt = f"""
Use ONLY the syllabus context.

Context:
{content}

Question:
{question}

Answer strictly in this format for a Class 10 student:

Concept (2-3 sentences)

Formula (if applicable)

Example (simple example)
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

    def explain_without_context(self, question: str):
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