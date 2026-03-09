from engine.lead_engine import LeadEngine
from engine.session_engine import SessionEngine
from engine.ux_lead_engine import UXLeadEngine
from engine.economics_engine import EconomicsEngine
from services.logging_service import LoggingService
from openai import OpenAI


class StudentSupportAgentV4:

    def __init__(
        self,
        rag_store,
        session_engine=None,
        ux_engine=None,
        lead_engine=None
    ):

        self.rag_store = rag_store

        self.session_engine = session_engine or SessionEngine()
        self.ux_engine = ux_engine or UXLeadEngine()
        self.lead_engine = lead_engine or LeadEngine()

        self.economics = EconomicsEngine()

        self.logger = LoggingService()

        self.client = OpenAI()

    # ====================================
    # MAIN ENTRY
    # ====================================

    def receive_question(self, question, context, session_id=None):

        subject = context.get("subject")
        chapter = context.get("chapter")

        self.logger.log("QUESTION_RECEIVED", {
            "question": question,
            "subject": subject,
            "chapter": chapter
        })

        # -----------------------------
        # RAG Retrieval
        # -----------------------------

        chunks = self.rag_store.search(
            question,
            subject,
            chapter
        )

        # -----------------------------
        # STRONG GUARDRAIL
        # -----------------------------

        if not chunks or len(chunks) < 2:

            escalation_code = "ESC_NO_VECTORS"
            escalation_reason = "No reliable syllabus content found"

            self.logger.log("ESCALATION_TRIGGERED", escalation_reason)

            confidence = self.session_engine.update_session(
                session_id,
                escalation_code
            )

            engagement_score = self.session_engine.get_engagement_score(
                session_id
            )

            intent_strength = self.session_engine.get_intent_strength(
                session_id
            )

            lead_id = self.lead_engine.process_escalation(
                session_id=session_id,
                subject=subject,
                chapter=chapter,
                question=question,
                escalation_code=escalation_code,
                escalation_reason=escalation_reason,
                confidence=confidence,
                engagement_score=engagement_score,
                intent_strength=intent_strength
            )

            prompt_user = self.ux_engine.evaluate(
                session_id,
                confidence,
                engagement_score
            )

            if prompt_user:

                return (
                    "ESCALATE TO SME: No reliable syllabus content found\n\n"
                    + self.ux_engine.get_prompt_message()
                )

            return "ESCALATE TO SME: No reliable syllabus content found"

        # -----------------------------
        # LLM ANSWER
        # -----------------------------

        try:

            prompt = f"""
Answer strictly from the syllabus content below.

Context:
{chunks}

Question:
{question}

Rules:
1. Use only the provided context.
2. If the answer is not present in the context, say:
"I could not find exact syllabus content."
"""

            response = self.client.chat.completions.create(

                model="gpt-4o-mini",

                messages=[
                    {"role": "system", "content": "You are a strict syllabus tutor."},
                    {"role": "user", "content": prompt}
                ],

                temperature=0

            )

            answer = response.choices[0].message.content.strip()

            self.logger.log("AGENT_RESULT", answer)

            return answer

        except Exception as e:

            self.logger.log("LLM_ERROR", str(e))

            return "Internal processing failure"