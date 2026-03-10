import os
from openai import OpenAI
from services.logging_service import LoggingService
from services.email_service import EmailService
from engine.lead_persistence import LeadPersistenceService
from engine.economics_engine import EscalationEconomicsEngine
from budget_guard import check_and_update


class StudentSupportAgentV4:

    def __init__(self, rag_store, session_engine=None, ux_engine=None, lead_engine=None):

        self.rag_store = rag_store
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.logger = LoggingService()

        self.session_engine = session_engine
        self.ux_engine = ux_engine
        self.lead_engine = lead_engine

        self.email_service = EmailService()

        # PostgreSQL Lead Persistence
        self.lead_persistence = LeadPersistenceService()

        # Block 13
        self.economics_engine = EscalationEconomicsEngine()

    # ==================================================
    # ENTRY POINT
    # ==================================================

    def receive_question(self, question, context, session_id="default"):

        intent, intent_strength = self.classify_intent(question)

        self.logger.log("INTENT_ANALYSIS", {
            "session_id": session_id,
            "intent": intent,
            "intent_strength": intent_strength
        })

        try:
            identified = self.identify_context(question, context)
        except Exception:
            return self.escalate(
                question,
                None,
                None,
                "Context identification failure",
                "ESC_CONTEXT_ERROR",
                session_id,
                intent_strength
            )

        if not identified or not isinstance(identified, dict):

            return self.escalate(
                question,
                None,
                None,
                "Invalid context generated",
                "ESC_CONTEXT_INVALID",
                session_id,
                intent_strength
            )

        if self.session_engine:

            self.session_engine.update_on_question(
                session_id,
                identified.get("chapter"),
                identified.get("difficulty")
            )

        try:
            decision = self.decide_action(identified)
        except Exception:

            return self.escalate(
                question,
                identified.get("subject"),
                identified.get("chapter"),
                "Decision engine failure",
                "ESC_DECISION_FAILURE",
                session_id,
                intent_strength
            )

        if decision == "RESPOND":

            try:
                return self.respond(question, identified, session_id, intent_strength)

            except Exception:

                return self.escalate(
                    question,
                    identified.get("subject"),
                    identified.get("chapter"),
                    "Response generation failure",
                    "ESC_RESPONSE_FAILURE",
                    session_id,
                    intent_strength
                )

        return self.escalate(
            question,
            identified.get("subject"),
            identified.get("chapter"),
            identified.get("escalation_reason", "Unknown reason"),
            identified.get("escalation_code", "ESC_UNKNOWN"),
            session_id,
            intent_strength
        )

    # ==================================================
    # INTENT DETECTION
    # ==================================================

    def classify_intent(self, question):

        q = question.lower()

        intent = "KNOWLEDGE_QUERY"
        strength = 0

        if any(k in q for k in ["prove", "derive", "theorem"]):
            intent = "ADVANCED_ACADEMIC"
            strength += 2

        if any(k in q for k in ["need help", "teacher", "tutor", "extra class"]):
            intent = "DIRECT_HELP_REQUEST"
            strength += 3

        if any(k in q for k in ["urgent", "exam tomorrow", "asap"]):
            intent = "HIGH_URGENCY"
            strength += 3

        if any(k in q for k in ["confused", "stuck", "not understanding"]):
            intent = "FRUSTRATION_SIGNAL"
            strength += 2

        return intent, strength

    # ==================================================
    # CONTEXT
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

    def decide_action(self, identified):

        if identified["difficulty"] == "advanced":

            identified["escalation_reason"] = "Advanced question requires teacher"
            identified["escalation_code"] = "ESC_ADVANCED_TOPIC"

            return "ESCALATE"

        return "RESPOND"

    # ==================================================
    # RESPONSE ENGINE
    # ==================================================

    def respond(self, question, identified, session_id, intent_strength):

        chunks = self.rag_store.search(
            question,
            identified["subject"],
            identified["chapter"]
        )

        if not chunks:

            if intent_strength >= 2:

                return self.escalate(
                    question,
                    identified["subject"],
                    identified["chapter"],
                    "No reliable syllabus content found",
                    "ESC_NO_VECTORS",
                    session_id,
                    intent_strength
                )

            return "I could not find exact syllabus content. Could you clarify your question?"

        if len(chunks) < 2:

            if intent_strength >= 2:

                return self.escalate(
                    question,
                    identified["subject"],
                    identified["chapter"],
                    "Insufficient retrieval confidence",
                    "ESC_LOW_CONFIDENCE",
                    session_id,
                    intent_strength
                )

            return "I found limited syllabus information. Could you clarify?"

        return self.explain_with_ai(question, chunks, session_id, intent_strength)

    # ==================================================
    # AI EXPLANATION ENGINE
    # ==================================================

    def explain_with_ai(self, question, chunks, session_id, intent_strength):

        content = "\n\n".join(chunks)

        exceeded, reason = check_and_update(0)

        if exceeded:

            return self.escalate(
                question,
                None,
                None,
                reason,
                "ESC_BUDGET_BLOCK",
                session_id,
                intent_strength
            )

        try:

            prompt = f"""
You are a friendly and supportive tutor helping a student understand concepts from their syllabus.

Use ONLY the syllabus content below.

Context:
{content}

Student Question:
{question}

Answer using this format:

1. Concept Explanation
Explain the concept clearly in simple language.

2. Key Formula (if relevant)
Show the formula and explain the variables.

3. Example
Provide a small example to make the idea easier.

Rules:
- Stay strictly within the provided context.
- Do not invent information outside the syllabus.
- Use a friendly tone suitable for students.

End with a short encouraging follow-up question.
Example:
"Would you like to see a quick example?"
"""

            response = self.client.chat.completions.create(

                model="gpt-4o-mini",

                max_tokens=350,

                messages=[
                    {"role": "system", "content": "You are a helpful academic tutor."},
                    {"role": "user", "content": prompt}
                ],

                temperature=0.2,

                timeout=8
            )

        except Exception:

            return self.escalate(
                question,
                None,
                None,
                "AI provider failure",
                "ESC_AI_TIMEOUT",
                session_id,
                intent_strength
            )

        answer = response.choices[0].message.content.strip()

        self.logger.log("AI_RESPONSE_GENERATED", {
            "session_id": session_id
        })

        return answer

    # ==================================================
    # ESCALATION
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

        lead_score = self.economics_engine.compute_lead_quality_score(
            escalation_confidence,
            engagement_score,
            intent_strength
        )

        priority = self.economics_engine.determine_priority(lead_score)

        if not self.economics_engine.escalation_budget_available():

            self.logger.log("ESCALATION_BLOCKED_BUDGET", {
                "session_id": session_id,
                "lead_score": lead_score
            })

            return "Escalation capacity is currently limited. Please try again shortly."

        self.economics_engine.register_escalation()

        self.logger.log("ESCALATION_TRIGGERED", {
            "session_id": session_id,
            "code": code,
            "reason": reason,
            "engagement_score": engagement_score,
            "intent_strength": intent_strength,
            "escalation_confidence": escalation_confidence,
            "lead_quality_score": lead_score,
            "priority": priority
        })

        lead_id = self.lead_persistence.upsert_lead(
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

        if escalation_confidence >= 40:

            subject_line = f"CurioNest Qualified Lead - {code}"

            body = f"""
Lead ID: {lead_id}
Session: {session_id}
Subject: {subject}
Chapter: {chapter}

Reason: {reason}

Confidence: {escalation_confidence}
Engagement Score: {engagement_score}
Intent Strength: {intent_strength}
Lead Quality Score: {lead_score}
Priority: {priority}
"""

            self.email_service.send_escalation(subject_line, body)

        if self.ux_engine:

            eligible = self.ux_engine.evaluate(
                session_id,
                escalation_confidence,
                engagement_score
            )

            if eligible:

                return (
                    f"ESCALATE TO SME: {reason}\n\n"
                    f"{self.ux_engine.get_prompt_message()}"
                )

        return f"ESCALATE TO SME: {reason}"

    # ==================================================
    # CONFIDENCE
    # ==================================================

    def compute_escalation_confidence(self, engagement_score, intent_strength, escalation_code=None):

        score = engagement_score * 2 + intent_strength * 5

        if escalation_code in {"ESC_ADVANCED_TOPIC", "ESC_KNOWLEDGE_GAP"}:
            score += 10

        return max(0, min(score, 100))

    # ==================================================
    # DIFFICULTY
    # ==================================================

    def detect_difficulty(self, question):

        if any(k in question.lower() for k in ["prove", "derive", "theorem"]):
            return "advanced"

        return "basic"