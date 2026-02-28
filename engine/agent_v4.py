import os
from openai import OpenAI
from services.logging_service import LoggingService
from budget_guard import check_and_update


class StudentSupportAgentV4:

    def __init__(self, rag_store, session_engine=None):
        self.rag_store = rag_store
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.logger = LoggingService()
        self.session_engine = session_engine

    # ================= ENTRY POINT =================

    def receive_question(self, question, context, session_id="default"):

        # ---- Intent Classification ----
        intent, intent_strength = self.classify_intent(question)

        self.logger.log("INTENT_ANALYSIS", {
            "session_id": session_id,
            "intent": intent,
            "intent_strength": intent_strength
        })

        try:
            identified = self.identify_context(question, context)
        except Exception:
            return self.escalate("Context identification failure", "ESC_CONTEXT_ERROR", session_id, intent_strength)

        if not identified or not isinstance(identified, dict):
            return self.escalate("Invalid context generated", "ESC_CONTEXT_INVALID", session_id, intent_strength)

        # ---- Session update ----
        if self.session_engine:
            self.session_engine.update_on_question(
                session_id,
                identified.get("chapter"),
                identified.get("difficulty")
            )

        try:
            decision = self.decide_action(identified)
        except Exception:
            return self.escalate("Decision engine failure", "ESC_DECISION_FAILURE", session_id, intent_strength)

        if decision == "RESPOND":
            try:
                return self.respond(question, identified, session_id, intent_strength)
            except Exception:
                return self.escalate("Response generation failure", "ESC_RESPONSE_FAILURE", session_id, intent_strength)

        return self.escalate(
            identified.get("escalation_reason", "Unknown reason"),
            identified.get("escalation_code", "ESC_UNKNOWN"),
            session_id,
            intent_strength
        )

    # ================= INTENT =================

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

    # ================= CONTEXT =================

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

    # ================= DECISION =================

    def decide_action(self, identified):

        if identified["difficulty"] == "advanced":
            identified["escalation_reason"] = "Advanced question requires teacher"
            identified["escalation_code"] = "ESC_ADVANCED_TOPIC"
            return "ESCALATE"

        return "RESPOND"

    # ================= RESPONSE =================

    def respond(self, question, identified, session_id, intent_strength):

        chunks = self.rag_store.search(
            question,
            identified["subject"],
            identified["chapter"]
        )

        if not chunks:
            return self.escalate(
                "No reliable syllabus content found",
                "ESC_NO_VECTORS",
                session_id,
                intent_strength
            )

        if len(chunks) < 2:
            return self.escalate(
                "Insufficient retrieval confidence",
                "ESC_LOW_CONFIDENCE",
                session_id,
                intent_strength
            )

        return self.explain_with_ai(question, chunks, session_id, intent_strength)

    # ================= AI =================

    def explain_with_ai(self, question, chunks, session_id, intent_strength):

        content = "\n".join(chunks)
        approx_tokens = len(content.split()) * 1.3

        if approx_tokens > 1200:
            return self.escalate(
                "Context too large for safe processing",
                "ESC_CONTEXT_TOO_LARGE",
                session_id,
                intent_strength
            )

        exceeded, reason = check_and_update(0)

        if exceeded:
            return self.escalate(reason, "ESC_BUDGET_BLOCK", session_id, intent_strength)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=300,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a strictly retrieval-bound academic assistant. "
                            "Answer ONLY using the provided content. "
                            "If the content is insufficient, say exactly: "
                            "'Insufficient information in provided syllabus content.'"
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Content:\n{content}\n\nQuestion:\n{question}"
                    }
                ],
                timeout=8
            )
        except Exception:
            return self.escalate(
                "AI provider failure",
                "ESC_AI_TIMEOUT",
                session_id,
                intent_strength
            )

        answer = response.choices[0].message.content

        if not answer:
            return self.escalate(
                "Empty AI response",
                "ESC_EMPTY_RESPONSE",
                session_id,
                intent_strength
            )

        if "Insufficient information" in answer:
            return self.escalate(
                "Knowledge base lacks required explanation",
                "ESC_KNOWLEDGE_GAP",
                session_id,
                intent_strength
            )

        return answer

    # ================= ESCALATION =================

    def escalate(self, reason, code, session_id, intent_strength=0):

        engagement_score = 0

        if self.session_engine:
            self.session_engine.update_on_escalation(session_id)
            engagement_score = self.session_engine.calculate_engagement_score(session_id)

        escalation_confidence = self.compute_escalation_confidence(
            engagement_score,
            intent_strength,
            code
        )

        self.logger.log("ESCALATION_TRIGGERED", {
            "session_id": session_id,
            "code": code,
            "reason": reason,
            "engagement_score": engagement_score,
            "intent_strength": intent_strength,
            "escalation_confidence": escalation_confidence
        })

        return f"ESCALATE TO SME: {reason}"

    # ================= CONFIDENCE SCORING =================

    def compute_escalation_confidence(self, engagement_score, intent_strength, escalation_code=None):

        score = 0

        # Base weights
        score += engagement_score * 2
        score += intent_strength * 5

        # High-signal escalation codes
        high_signal_codes = {
            "ESC_ADVANCED_TOPIC",
            "ESC_KNOWLEDGE_GAP"
        }

        if escalation_code in high_signal_codes:
            score += 10

        # Noise suppression
        low_signal_codes = {
            "ESC_NO_VECTORS",
            "ESC_LOW_CONFIDENCE",
            "ESC_CONTEXT_TOO_LARGE",
            "ESC_BUDGET_BLOCK",
            "ESC_AI_TIMEOUT"
        }

        if escalation_code in low_signal_codes:
            score -= 5

        return max(0, min(score, 100))

    # ================= DIFFICULTY =================

    def detect_difficulty(self, question):

        for k in ["prove", "derive", "theorem"]:
            if k in question.lower():
                return "advanced"

        return "basic"