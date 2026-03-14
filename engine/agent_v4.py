import os
import re
from openai import OpenAI

from services.logging_service import LoggingService
from services.email_service import EmailService

from engine.lead_persistence import LeadPersistenceService
from engine.economics_engine import EscalationEconomicsEngine

from budget_guard import check_and_update


# ==============================
# LATEX NORMALIZER
# ==============================

def normalize_latex(text: str):

    if not text:
        return text

    text = re.sub(r"\\\((.*?)\\\)", r"\\[\1\\]", text)
    text = re.sub(r"\\([A-Za-z0-9_+\-\^=]+)\\", r"\\[\1\\]", text)
    text = re.sub(r"(?:\b[a-zA-Z]\n){3,}", "", text)

    return text


# ==============================
# AGENT V5
# ==============================

class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine=None, ux_engine=None, lead_engine=None):

        self.rag_store = rag_store

        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )

        self.logger = LoggingService()

        self.session_engine = session_engine
        self.ux_engine = ux_engine
        self.lead_engine = lead_engine

        self.email_service = EmailService()
        self.lead_persistence = LeadPersistenceService()
        self.economics_engine = EscalationEconomicsEngine()

    # ==================================================
    # ENTRY POINT
    # ==================================================

    def receive_question(self, question, context, session_id="default"):

        intent, intent_conf = self.classify_intent_ai(question)

        self.logger.log("INTENT_ANALYSIS_V5", {
            "session_id": session_id,
            "intent": intent,
            "confidence": intent_conf
        })

        identified = self.identify_context(question, context)

        if self.session_engine:

            self.session_engine.update_on_question(
                session_id,
                identified.get("chapter"),
                identified.get("difficulty")
            )

        decision = self.decide_action(
            question,
            identified,
            intent,
            intent_conf,
            session_id
        )

        if decision == "RESPOND":

            try:

                return self.respond(
                    question,
                    identified,
                    session_id,
                    intent_conf
                )

            except Exception:

                return self.escalate(
                    question,
                    identified.get("subject"),
                    identified.get("chapter"),
                    "Response generation failure",
                    "ESC_RESPONSE_FAILURE",
                    session_id,
                    intent_conf
                )

        return self.escalate(
            question,
            identified.get("subject"),
            identified.get("chapter"),
            "Student likely needs teacher assistance",
            "ESC_LEARNING_SUPPORT",
            session_id,
            intent_conf
        )

    # ==================================================
    # AI INTENT CLASSIFIER
    # ==================================================

    def classify_intent_ai(self, question):

        prompt = f"""
Classify the student's learning intent.

Question:
{question}

Possible intents:
- BASIC_CONCEPT
- ADVANCED_TOPIC
- CONFUSED_STUDENT
- DIRECT_HELP_REQUEST
- EXAM_URGENCY

Return JSON:
{{"intent":"...", "confidence":0.0-1.0}}
"""

        try:

            res = self.client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=60,
                temperature=0,
                messages=[
                    {"role": "system", "content": "You analyze student questions."},
                    {"role": "user", "content": prompt}
                ]
            )

            text = res.choices[0].message.content

            if "ADVANCED_TOPIC" in text:
                return "ADVANCED_TOPIC", 0.8

            if "CONFUSED_STUDENT" in text:
                return "CONFUSED_STUDENT", 0.7

            if "DIRECT_HELP_REQUEST" in text:
                return "DIRECT_HELP_REQUEST", 0.9

            return "BASIC_CONCEPT", 0.5

        except Exception:

            return "KNOWLEDGE_QUERY", 0.4

    # ==================================================
    # CONTEXT IDENTIFICATION
    # ==================================================

    def identify_context(self, question, context):

        subject = context.get("subject")
        chapter = context.get("chapter")

        difficulty = self.detect_difficulty(question)

        return {
            "question": question,
            "subject": subject,
            "chapter": chapter,
            "difficulty": difficulty
        }

    # ==================================================
    # DECISION ENGINE
    # ==================================================

    def decide_action(self, question, identified, intent, intent_conf, session_id):

        escalation_score = 0

        if intent == "ADVANCED_TOPIC":
            escalation_score += 8

        if intent == "DIRECT_HELP_REQUEST":
            escalation_score += 10

        if intent == "CONFUSED_STUDENT":
            escalation_score += 6

        if self.session_engine:

            engagement = self.session_engine.calculate_engagement_score(session_id)
            escalation_score += engagement * 2

        if identified["difficulty"] == "advanced":
            escalation_score += 5

        self.logger.log("ESCALATION_SCORE", {
            "score": escalation_score,
            "intent": intent
        })

        if escalation_score >= 12:
            return "ESCALATE"

        return "RESPOND"

    # ==================================================
    # RESPONSE ENGINE
    # ==================================================

    def respond(self, question, identified, session_id, intent_conf):

        chunks = self.rag_store.search(
            question,
            identified["subject"],
            identified["chapter"]
        )

        if not chunks:
            return self.curiosity_response(question, identified)

        if len(chunks) < 2:

            if intent_conf >= 0.7:

                return self.escalate(
                    question,
                    identified["subject"],
                    identified["chapter"],
                    "Low syllabus coverage",
                    "ESC_LOW_CONFIDENCE",
                    session_id,
                    intent_conf
                )

            return "I found limited syllabus information. Could you clarify your question?"

        return self.explain_with_ai(question, chunks, session_id)

    # ==================================================
    # AI TUTOR
    # ==================================================

    def explain_with_ai(self, question, chunks, session_id):

        content = "\n\n".join(chunks)

        exceeded, reason = check_and_update(0)

        if exceeded:

            return self.escalate(
                question,
                None,
                None,
                reason,
                "ESC_BUDGET_BLOCK",
                session_id
            )

        prompt = f"""
You are a friendly tutor helping a student.

Use ONLY this syllabus context.

Context:
{content}

Question:
{question}

Answer structure:

1. Concept Explanation
2. Formula if needed
3. Simple Example

Use LaTeX for formulas:

\\[
F = ma
\\]
"""

        response = self.client.chat.completions.create(

            model="gpt-4o-mini",

            max_tokens=350,

            temperature=0.2,

            messages=[
                {"role": "system", "content": "You are an academic tutor."},
                {"role": "user", "content": prompt}
            ]
        )

        answer = response.choices[0].message.content.strip()

        answer = normalize_latex(answer)

        self.logger.log("AI_RESPONSE_GENERATED_V5", {
            "session_id": session_id
        })

        return answer

    # ==================================================
    # CURIOSITY RESPONSE
    # ==================================================

    def curiosity_response(self, question, identified):

        exceeded, _ = check_and_update(0)

        if exceeded:
            return "Let's stay focused on your syllabus topic."

        prompt = f"""
The student asked:

{question}

This topic is outside the syllabus.

Explain briefly in two short paragraphs.

Then redirect to:

Subject: {identified["subject"]}
Chapter: {identified["chapter"]}
"""

        res = self.client.chat.completions.create(

            model="gpt-4o-mini",

            max_tokens=120,

            temperature=0.2,

            messages=[
                {"role": "system", "content": "You are a helpful academic tutor."},
                {"role": "user", "content": prompt}
            ]
        )

        answer = res.choices[0].message.content.strip()

        return normalize_latex(answer)

    # ==================================================
    # ESCALATION ENGINE
    # ==================================================

    def escalate(self, question, subject, chapter, reason, code, session_id, intent_strength=0):

        engagement_score = 0

        if self.session_engine:

            self.session_engine.update_on_escalation(session_id)

            engagement_score = self.session_engine.calculate_engagement_score(session_id)

        escalation_confidence = self.compute_escalation_confidence(
            engagement_score,
            intent_strength,
            code
        )

        if not self.economics_engine.escalation_budget_available():
            return "Escalation capacity is currently limited."

        self.economics_engine.register_escalation()

        self.lead_persistence.upsert_lead(
            session_id=session_id,
            subject=subject,
            chapter=chapter,
            question=question,
            escalation_code=code,
            escalation_reason=reason,
            confidence=escalation_confidence,
            engagement_score=engagement_score,
            intent_strength=intent_strength,
            status="QUALIFIED" if escalation_confidence >= 40 else "NEW"
        )

        return f"ESCALATE TO SME: {reason}"

    # ==================================================
    # CONFIDENCE SCORE
    # ==================================================

    def compute_escalation_confidence(self, engagement_score, intent_strength, escalation_code=None):

        score = engagement_score * 2 + intent_strength * 5

        if escalation_code in {"ESC_ADVANCED_TOPIC", "ESC_KNOWLEDGE_GAP"}:
            score += 10

        return max(0, min(score, 100))

    # ==================================================
    # DIFFICULTY DETECTION
    # ==================================================

    def detect_difficulty(self, question):

        q = question.lower()

        if any(k in q for k in [
            "prove",
            "derive",
            "theorem",
            "resonance",
            "quantum",
            "orbital",
            "calculus"
        ]):
            return "advanced"

        return "basic"