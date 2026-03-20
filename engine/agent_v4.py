import os
import re
from openai import OpenAI

from engine.cache_engine import CacheEngine
from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# ================= CLEAN =================
def clean(text):
    if not text:
        return text

    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text)
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text)
    text = re.sub(r"\\frac\{(.*?)\}\{(.*?)\}", r"\1/\2", text)
    text = re.sub(r"\\sqrt\{(.*?)\}", r"sqrt(\1)", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
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

        # scoped per subject+chapter
        self.session_state = {}

    # ================= MAIN =================
    def receive_question(self, question, context, session_id):

        try:
            question = question.strip()
            subject = context.get("subject")
            chapter = context.get("chapter")

            key = f"{session_id}_{subject}_{chapter}"

            if key not in self.session_state:
                self.session_state[key] = {
                    "confusion": 0,
                    "repetition": 0,
                    "last_question": "",
                    "escalated": False,
                    "rejection_count": 0
                }

            state = self.session_state[key]

            # ---------- SMALL TALK ----------
            if self._is_smalltalk(question):
                return {"type": "smalltalk", "message": "Ask me anything from your chapter 😊"}

            # ---------- CACHE ----------
            cached = self.cache.lookup(question, subject, chapter)
            if cached:
                return {"type": "answer", "message": cached}

            # ---------- INTENT ----------
            intent = self._intent(question)

            # ---------- USER REJECTION ----------
            if "dont need teacher" in question.lower():
                state["rejection_count"] += 1
                return {"type": "answer", "message": "Alright 👍 Let’s continue. Ask your doubt."}

            # ---------- HELP ----------
            if intent == "HELP":
                return self._escalate(question, subject, chapter, session_id)

            # ---------- EMOTIONAL ----------
            if intent == "EMOTIONAL":
                return self._escalate(question, subject, chapter, session_id)

            # ---------- SUBJECT CHECK ----------
            if self._is_wrong_subject(question, subject):
                return {
                    "type": "answer",
                    "message": "This seems from a different subject. I can help briefly, but please select correct Subject & Chapter."
                }

            # ---------- REPETITION ----------
            if question.lower() == state["last_question"].lower():
                state["repetition"] += 1
            else:
                state["repetition"] = 0

            state["last_question"] = question

            # ---------- CONFUSION ----------
            if intent == "CONFUSION":
                state["confusion"] += 1

            # ---------- ESCALATION LOGIC ----------
            if not state["escalated"]:

                if state["confusion"] >= 3 or state["repetition"] >= 3:
                    return self._escalate(question, subject, chapter, session_id)

            # ---------- HYBRID CASES ----------
            if self._is_numerical(question) or self._is_advanced(question):
                answer = self._answer(question, subject, chapter)

                return {
                    "type": "answer",
                    "message": clean(answer) + "\n\nWant help from a teacher?"
                }

            if self._is_exam_query(question):
                answer = self._answer(question, subject, chapter)

                return {
                    "type": "answer",
                    "message": clean(answer) + "\n\nThis topic is important. A teacher can guide you better."
                }

            # ---------- NORMAL FLOW ----------
            if state["confusion"] == 0:
                answer = self._answer(question, subject, chapter)
            elif state["confusion"] == 1:
                answer = self._simplify(question)
            else:
                answer = self._example(question)

            answer = clean(answer)

            self.cache.store(question, subject, chapter, answer)

            return {"type": "answer", "message": answer}

        except Exception as e:
            self.logger.log("AGENT_ERROR", str(e))
            return {"type": "error", "message": "System error."}

    # ================= INTENT =================
    def _intent(self, question):

        q = question.lower()

        if any(x in q for x in ["dont understand", "not clear", "confused", "again"]):
            return "CONFUSION"

        if any(x in q for x in ["teacher", "tuition", "help me"]):
            return "HELP"

        if any(x in q for x in ["fail", "scared", "weak"]):
            return "EMOTIONAL"

        return "NORMAL"

    # ================= TYPE DETECTION =================
    def _is_numerical(self, q):
        return any(x in q.lower() for x in ["solve", "find", "calculate"])

    def _is_exam_query(self, q):
        return any(x in q.lower() for x in ["important", "exam", "tips"])

    def _is_advanced(self, q):
        return any(x in q.lower() for x in ["derive", "prove"])

    def _is_wrong_subject(self, q, subject):
        q = q.lower()

        if subject == "physics" and any(x in q for x in ["cell", "mitochondria"]):
            return True

        if subject == "chemistry" and any(x in q for x in ["force", "velocity"]):
            return True

        return False

    # ================= ANSWERS =================
    def _answer(self, q, subject, chapter):

        context = self._context(q, subject, chapter)

        return self._llm(f"""
Explain clearly in short:

Definition
Key Idea
Example (if needed)

No latex.

Question: {q}
Context: {context}
""")

    def _simplify(self, q):

        return self._llm(f"""
Explain very simply in 2 lines.

Question: {q}
""")

    def _example(self, q):

        return self._llm(f"""
Explain with simple example.

Question: {q}
""")

    # ================= HELPERS =================
    def _context(self, q, s, c):
        try:
            return "".join(self.rag_store.search(q, s, c))
        except:
            return ""

    def _llm(self, prompt):
        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content

    def _is_smalltalk(self, q):
        return len(q.strip()) < 6

    # ================= ESCALATION =================
    def _escalate(self, q, s, c, sid):

        key = f"{sid}_{s}_{c}"
        state = self.session_state[key]

        if state["rejection_count"] >= 2:
            return {"type": "answer", "message": "Let’s continue learning 👍"}

        state["escalated"] = True

        try:
            self.lead_persistence.upsert_lead(
                session_id=sid,
                subject=s,
                chapter=c,
                question=q,
                escalation_code="ESC",
                escalation_reason="conversion_trigger",
                confidence=0.9,
                engagement_score=0,
                intent_strength=0.9,
                status="NEW"
            )
        except:
            pass

        return {
            "type": "escalation",
            "message": "A teacher can guide you better on this."
        }