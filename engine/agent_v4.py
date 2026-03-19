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

    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text)
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text)
    text = re.sub(r"\\text\{(.*?)\}", r"\1", text)
    text = re.sub(r"\s+", " ", text)

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

    # ============================================
    # MAIN ENTRY
    # ============================================

    def receive_question(self, question, context, session_id):

        try:
            question = question.strip()
            subject = context.get("subject")
            chapter = context.get("chapter")

            # ---------------- CACHE ----------------
            cached = self.cache.lookup(question, subject, chapter)
            if cached:
                return {"type": "answer", "message": cached}

            if self.session_engine:
                self.session_engine.store_message(session_id, "user", question)

            # ---------------- INTENT ----------------
            intent = self._intent(question)

            # soft signal boost (NOT hard rules)
            if self._soft_confusion_signal(question):
                intent = "CONFUSION"

            is_numerical = bool(re.search(r"\d", question))

            count = self.session_confusion.get(session_id, 0)

            # ---------------- CONFUSION TRACK ----------------
            if intent == "CONFUSION":
                count += 1
            elif intent == "NORMAL":
                count = max(0, count - 1)  # gradual decay (human-like)
            
            self.session_confusion[session_id] = count

            # ---------------- ESCALATION ----------------
            if not self.session_escalated.get(session_id):

                if not is_numerical:

                    if intent == "HELP":
                        self.session_escalated[session_id] = True
                        return self._escalate(question, subject, chapter, session_id)

                    if count >= 3:
                        self.session_escalated[session_id] = True
                        return self._escalate(question, subject, chapter, session_id)

            # ---------------- ANSWER ----------------
            if intent == "CONFUSION" and count >= 1:
                answer = self._answer_with_recovery(question, subject, chapter)
            else:
                answer = self._answer(question, subject, chapter)

            answer = normalize_latex(answer)

            self.cache.store(question, subject, chapter, answer)

            if self.session_engine:
                self.session_engine.store_message(session_id, "assistant", answer)

            return {"type": "answer", "message": answer}

        except Exception as e:
            self.logger.log("AGENT_ERROR", str(e))
            return {
                "type": "error",
                "message": "System temporarily unavailable."
            }

    # ============================================
    # INTENT (AI FIRST)
    # ============================================

    def _intent(self, question):

        prompt = f"""
You are detecting student learning state.

Classify into ONE:

NORMAL → student asking or learning
CONFUSION → student struggling or not understanding
HELP → student wants teacher/tutor

IMPORTANT:
- Short phrases like "confused", "not sure", "didn't get it" = CONFUSION
- Even broken English should be understood

Question:
{question}

Return ONLY one word.
"""

        try:
            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=5,
                messages=[
                    {"role": "system", "content": "Strict classifier."},
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
    # SOFT SIGNAL (NOT HARD CODING)
    # ============================================

    def _soft_confusion_signal(self, q):
        q = q.lower()

        # pattern-based (not strict keywords)
        return (
            len(q) < 25 and (
                "confus" in q or
                "not" in q and "understand" in q or
                "clear" in q or
                "again" in q
            )
        )

    # ============================================
    # ANSWER (RAG + GENERAL)
    # ============================================

    def _answer(self, question, subject, chapter):

        try:
            chunks = self.rag_store.search(question, subject, chapter)
        except:
            chunks = []

        if chunks:
            context = "".join(chunks)
        else:
            context = ""

        prompt = f"""
You are a friendly teacher.

Rules:
- Be clear and simple
- Do NOT change topic
- Use relatable explanation
- Avoid robotic tone

Context:
{context}

Question:
{question}
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}]
        )

        return res.choices[0].message.content

    # ============================================
    # RECOVERY ANSWER (HUMAN-LIKE)
    # ============================================

    def _answer_with_recovery(self, question, subject, chapter):

        prompt = f"""
Student is confused.

Re-explain more simply:
- Use analogy
- Break into steps
- Be very clear
- Sound human and supportive

Question:
{question}
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.5,
            messages=[{"role": "user", "content": prompt}]
        )

        return res.choices[0].message.content

    # ============================================
    # ESCALATION
    # ============================================

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
            "message": "It seems this topic needs personal guidance. A teacher can help you better."
        }