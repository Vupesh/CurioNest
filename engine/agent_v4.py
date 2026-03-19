import os
import re
from openai import OpenAI
from engine.cache_engine import CacheEngine
from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def normalize_latex(text):
    if not text:
        return text

    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.DOTALL)
    text = re.sub(r"\\text\{(.*?)\}", r"\1", text)
    text = re.sub(r"\${3,}", "$$", text)

    return text.strip()


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

    def receive_question(self, question, context, session_id):

        try:

            question = question.strip()
            subject = context.get("subject")
            chapter = context.get("chapter")

            # CACHE
            cached = self.cache.lookup(question, subject, chapter)
            if cached:
                return {"type": "answer", "message": cached}

            # MEMORY
            if self.session_engine:
                self.session_engine.store_message(session_id, "user", question)

            intent = self._intent(question)
            is_numerical = bool(re.search(r"\d", question))

            try:
                chunks = self.rag_store.search(question, subject, chapter)
            except:
                chunks = []

            # ESCALATION CONTROL
            if not self.session_escalated.get(session_id):

                count = self.session_confusion.get(session_id, 0)

                if intent in ["CONFUSION", "HELP"]:
                    count += 1
                    self.session_confusion[session_id] = count

                if not is_numerical:

                    if count >= 3:
                        self.session_escalated[session_id] = True
                        return self._escalate(question, subject, chapter, session_id)

                    if "teacher" in question.lower():
                        self.session_escalated[session_id] = True
                        return self._escalate(question, subject, chapter, session_id)

            # ANSWER
            if chunks:
                answer = self._answer_rag(question, chunks)
            else:
                answer = self._answer_general(question)

            answer = normalize_latex(answer)

            self.cache.store(question, subject, chapter, answer)

            if self.session_engine:
                self.session_engine.store_message(session_id, "assistant", answer)

            return {"type": "answer", "message": answer}

        except:
            return {"type": "error", "message": "System temporarily unavailable."}

    def _intent(self, q):
        q = q.lower()
        if "confused" in q or "not understand" in q:
            return "CONFUSION"
        if "help" in q or "teacher" in q:
            return "HELP"
        return "NORMAL"

    def _answer_rag(self, question, chunks):

        prompt = f"""
Use context:

{''.join(chunks)}

Answer simply.
Use $$ for formulas only.
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt + question}]
        )

        return res.choices[0].message.content

    def _answer_general(self, question):

        prompt = f"""
Answer clearly.
Use $$ for formulas only.
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt + question}]
        )

        return res.choices[0].message.content

    def _escalate(self, question, subject, chapter, session_id):

        try:
            self.lead_persistence.upsert_lead(
                session_id=session_id,
                subject=subject,
                chapter=chapter,
                question=question,
                escalation_code="ESC",
                escalation_reason="help_needed",
                confidence=0.8,
                engagement_score=0,
                intent_strength=0.8,
                status="NEW"
            )
        except:
            pass

        return {
            "type": "escalation",
            "message": "A teacher will contact you shortly."
        }