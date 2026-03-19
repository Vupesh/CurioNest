import os
import re
from openai import OpenAI

from engine.cache_engine import CacheEngine
from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# =============================
# CLEAN OUTPUT (NO LATEX ISSUES)
# =============================

def normalize_latex(text):
    if not text:
        return text

    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text)
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text)
    text = re.sub(r"\\text\{(.*?)\}", r"\1", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =============================
# AGENT
# =============================

class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine=None):

        self.rag_store = rag_store
        self.session_engine = session_engine

        self.cache = CacheEngine()
        self.logger = LoggingService()
        self.lead_persistence = LeadPersistenceService()

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # session behavior tracking
        self.session_confusion = {}
        self.session_escalated = {}

    # =============================
    # ENTRY POINT
    # =============================

    def receive_question(self, question, context, session_id):

        try:
            question = question.strip()
            subject = context.get("subject")
            chapter = context.get("chapter")

            # -------------------------
            # CACHE (FAST PATH)
            # -------------------------
            cached = self.cache.lookup(question, subject, chapter)
            if cached:
                return {"type": "answer", "message": cached}

            # -------------------------
            # SESSION MEMORY
            # -------------------------
            if self.session_engine:
                self.session_engine.store_message(session_id, "user", question)

            # -------------------------
            # AI INTENT DETECTION (FIXED)
            # -------------------------
            intent = self._intent(question)

            # detect numerical
            is_numerical = bool(re.search(r"\d", question))

            # -------------------------
            # RAG
            # -------------------------
            try:
                chunks = self.rag_store.search(question, subject, chapter)
            except:
                chunks = []

            # -------------------------
            # ESCALATION LOGIC
            # -------------------------
            if not self.session_escalated.get(session_id):

                count = self.session_confusion.get(session_id, 0)

                if intent in ["CONFUSION", "HELP"]:
                    count += 1
                    self.session_confusion[session_id] = count

                # avoid numerical escalation
                if not is_numerical:

                    if count >= 3:
                        self.session_escalated[session_id] = True
                        return self._escalate(question, subject, chapter, session_id)

                    if intent == "HELP":
                        self.session_escalated[session_id] = True
                        return self._escalate(question, subject, chapter, session_id)

            # -------------------------
            # ANSWER GENERATION
            # -------------------------
            if chunks:
                answer = self._answer_rag(question, chunks)
            else:
                answer = self._answer_general(question)

            answer = normalize_latex(answer)

            # -------------------------
            # CACHE STORE
            # -------------------------
            self.cache.store(question, subject, chapter, answer)

            # -------------------------
            # SESSION MEMORY STORE
            # -------------------------
            if self.session_engine:
                self.session_engine.store_message(session_id, "assistant", answer)

            return {"type": "answer", "message": answer}

        except Exception as e:

            self.logger.log("AGENT_ERROR", str(e))

            return {
                "type": "error",
                "message": "System temporarily unavailable."
            }

    # =============================
    # AI INTENT (FINAL FIX)
    # =============================

    def _intent(self, question):

        prompt = f"""
Classify the student's intent.

Return ONLY one word:

NORMAL
CONFUSION
HELP

Examples:
"I don't understand this" → CONFUSION
"Explain again please" → CONFUSION
"Can a teacher help me?" → HELP
"What is force?" → NORMAL

Question:
{question}
"""

        try:

            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=5,
                messages=[
                    {"role": "system", "content": "Return only one word."},
                    {"role": "user", "content": prompt}
                ]
            )

            intent = res.choices[0].message.content.strip().upper()

            if intent not in ["NORMAL", "CONFUSION", "HELP"]:
                return "NORMAL"

            return intent

        except:
            return "NORMAL"

    # =============================
    # RAG ANSWER
    # =============================

    def _answer_rag(self, question, chunks):

        prompt = f"""
Explain clearly like a teacher.

Rules:
- Use simple equations (F = m × a)
- DO NOT use LaTeX syntax
- Keep answer structured and simple

Context:
{''.join(chunks)}

Question:
{question}
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return res.choices[0].message.content

    # =============================
    # GENERAL ANSWER
    # =============================

    def _answer_general(self, question):

        prompt = f"""
Explain clearly like a teacher.

Rules:
- Use simple equations (KE = 1/2 mv^2)
- DO NOT use LaTeX syntax
- Keep it clean and beginner-friendly

Question:
{question}
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return res.choices[0].message.content

    # =============================
    # ESCALATION
    # =============================

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
            "message": "A teacher will contact you shortly."
        }