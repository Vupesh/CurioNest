import os
import re
from openai import OpenAI

from engine.cache_engine import CacheEngine
from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def normalize_latex(text):
    return re.sub(r"\s+", " ", text).strip() if text else text


class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine=None):

        self.rag_store = rag_store
        self.session_engine = session_engine

        self.cache = CacheEngine()
        self.logger = LoggingService()
        self.lead_persistence = LeadPersistenceService()

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.session_confusion = {}
        self.session_escalated = {}

    # ============================================
    # MAIN
    # ============================================

    def receive_question(self, question, context, session_id):

        try:
            question = question.strip()
            subject = context.get("subject")
            chapter = context.get("chapter")

            # -------- SMART GUARDRAIL --------
            guard = self._guardrail(question)
            if guard:
                return guard

            # -------- CACHE --------
            cached = self.cache.lookup(question, subject, chapter)
            if cached:
                return {"type": "answer", "message": cached}

            # -------- MEMORY --------
            history = []
            if self.session_engine:
                self.session_engine.store_message(session_id, "user", question)
                history = self.session_engine.get_recent_messages(session_id, 5)

            # -------- INTENT --------
            intent = self._intent(question)

            is_numerical = bool(re.search(r"\d", question))
            count = self.session_confusion.get(session_id, 0)

            # -------- CONFUSION TRACK --------
            if intent == "CONFUSION":
                count += 1
            elif intent == "NORMAL":
                count = max(0, count - 1)

            self.session_confusion[session_id] = count

            # -------- ESCALATION --------
            if not self.session_escalated.get(session_id):

                if not is_numerical and len(question) > 15:

                    if intent == "HELP":
                        return self._trigger_escalation(question, subject, chapter, session_id)

                    if count >= 3:
                        return self._trigger_escalation(question, subject, chapter, session_id)

            # -------- ANSWER STRATEGY --------
            if count == 0:
                answer = self._answer(question, subject, chapter, history)

            elif count == 1:
                answer = self._answer_simplified(question, subject, chapter)

            else:
                answer = self._answer_with_example(question, subject, chapter)

            answer = normalize_latex(answer)

            self.cache.store(question, subject, chapter, answer)

            if self.session_engine:
                self.session_engine.store_message(session_id, "assistant", answer)

            return {"type": "answer", "message": answer}

        except Exception as e:
            self.logger.log("AGENT_ERROR", str(e))
            return {"type": "error", "message": "System temporarily unavailable."}

    # ============================================
    # SMART GUARDRAIL (AI BASED)
    # ============================================

    def _guardrail(self, question):

        prompt = f"""
Classify this input:

SMALLTALK → greeting, casual, emotional, irrelevant
STUDY → actual academic question

Input:
{question}

Return ONE word.
"""

        try:
            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=3,
                messages=[
                    {"role": "system", "content": "Classifier"},
                    {"role": "user", "content": prompt}
                ]
            )

            result = res.choices[0].message.content.strip().upper()

            if result == "SMALLTALK":
                return {
                    "type": "smalltalk",
                    "message": "I’m here to help with your studies 😊 Ask me any question from your chapter."
                }

        except:
            pass

        return None

    # ============================================
    # INTENT
    # ============================================

    def _intent(self, question):

        prompt = f"""
Classify intent:

NORMAL / CONFUSION / HELP

CONFUSION includes:
- not understanding
- asking to explain again
- asking for examples

Question:
{question}
"""

        try:
            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=5,
                messages=[
                    {"role": "system", "content": "Strict classifier"},
                    {"role": "user", "content": prompt}
                ]
            )

            intent = res.choices[0].message.content.strip().upper()

            if intent in ["NORMAL", "CONFUSION", "HELP"]:
                return intent

        except:
            pass

        return "NORMAL"

    # ============================================
    # ANSWERS
    # ============================================

    def _answer(self, question, subject, chapter, history):

        context = self._get_context(question, subject, chapter)

        prompt = f"""
Explain clearly like a teacher:

- Definition
- Key idea
- Simple explanation

Stay on topic.

Question:
{question}

Context:
{context}
"""

        return self._llm(prompt)

    def _answer_simplified(self, question, subject, chapter):

        prompt = f"""
Explain very simply in 2-3 lines.

Question:
{question}
"""
        return self._llm(prompt)

    def _answer_with_example(self, question, subject, chapter):

        prompt = f"""
Explain with a simple example or numerical.

Question:
{question}
"""
        return self._llm(prompt)

    # ============================================
    # HELPERS
    # ============================================

    def _get_context(self, question, subject, chapter):
        try:
            chunks = self.rag_store.search(question, subject, chapter)
            return "".join(chunks)
        except:
            return ""

    def _llm(self, prompt):
        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content

    # ============================================
    # ESCALATION
    # ============================================

    def _trigger_escalation(self, question, subject, chapter, session_id):
        self.session_escalated[session_id] = True
        return self._escalate(question, subject, chapter, session_id)

    def _escalate(self, question, subject, chapter, session_id):

        try:
            self.lead_persistence.upsert_lead(
                session_id=session_id,
                subject=subject,
                chapter=chapter,
                question=question,
                escalation_code="ESC",
                escalation_reason="student_struggling",
                confidence=0.85,
                engagement_score=0,
                intent_strength=0.85,
                status="NEW"
            )
        except Exception as e:
            self.logger.log("ESCALATION_DB_FAIL", str(e))

        return {
            "type": "escalation",
            "message": "Let me connect you with a teacher for better guidance."
        }