import os
import re
from openai import OpenAI

from engine.cache_engine import CacheEngine
from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# ================= CLEAN (NO LATEX EVER) =================
def clean(text):
    if not text:
        return text

    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text)
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text)
    text = re.sub(r"\\frac\{(.*?)\}\{(.*?)\}", r"\1/\2", text)
    text = re.sub(r"\\sqrt\{(.*?)\}", r"sqrt(\1)", text)
    text = re.sub(r"\\times", "×", text)
    text = re.sub(r"\\cdot", "·", text)
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

        self.session_confusion = {}
        self.session_escalated = {}

    # ================= MAIN =================
    def receive_question(self, question, context, session_id):

        try:
            question = question.strip()
            subject = context.get("subject")
            chapter = context.get("chapter")

            # ---------- SMALL TALK ----------
            if self._is_smalltalk(question):
                return {
                    "type": "smalltalk",
                    "message": "Ask me anything from your chapter 😊"
                }

            # ---------- CACHE ----------
            cached = self.cache.lookup(question, subject, chapter)
            if cached:
                return {"type": "answer", "message": cached}

            # ---------- INTENT ----------
            intent = self._intent(question)

            # ---------- DIRECT HELP ----------
            if intent == "HELP":
                return self._escalate(question, subject, chapter, session_id)

            # ---------- EMOTIONAL ----------
            if intent == "EMOTIONAL":
                return {
                    "type": "answer",
                    "message": "You’ll do fine 👍 Focus on concepts step by step. I’m here to help."
                }

            # ---------- CONFUSION TRACK ----------
            count = self.session_confusion.get(session_id, 0)

            if intent == "CONFUSION":
                count += 1
            elif intent == "NORMAL":
                count = max(0, count - 1)

            self.session_confusion[session_id] = count

            # ---------- ESCALATION ----------
            if not self.session_escalated.get(session_id):
                if count >= 3:
                    return self._escalate(question, subject, chapter, session_id)

            # ---------- ANSWER STRATEGY ----------
            if count == 0:
                answer = self._answer(question, subject, chapter)

            elif count == 1:
                answer = self._simplify(question, subject, chapter)

            else:
                answer = self._example(question, subject, chapter)

            answer = clean(answer)

            self.cache.store(question, subject, chapter, answer)

            return {"type": "answer", "message": answer}

        except Exception as e:
            self.logger.log("AGENT_ERROR", str(e))
            return {"type": "error", "message": "System error."}

    # ================= INTENT =================
    def _intent(self, question):

        prompt = f"""
Classify intent:

NORMAL → valid academic question
CONFUSION → student not understanding
HELP → wants teacher
EMOTIONAL → fear, pass/fail, reassurance

IMPORTANT:
- "Explain more" = NORMAL
- "Explain with example" = NORMAL
- "I don't understand" = CONFUSION
- "talk to teacher" = HELP

Question:
{question}

Return one word.
"""

        try:
            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=5,
                messages=[{"role": "user", "content": prompt}]
            )

            out = res.choices[0].message.content.strip().upper()

            if out in ["NORMAL", "CONFUSION", "HELP", "EMOTIONAL"]:
                return out

        except:
            pass

        return "NORMAL"

    # ================= ANSWER =================
    def _answer(self, q, subject, chapter):

        context = self._context(q, subject, chapter)

        prompt = f"""
You are a teacher for {subject}.

RULES:
- Answer ANY question related to {subject}
- Do NOT reject valid subject questions
- Use context if available, else use knowledge
- Reject ONLY if clearly from a different subject
- NO LATEX

Explain:
1. Definition
2. Key idea
3. Simple explanation

Question: {q}
Context: {context}
"""

        return self._llm(prompt)

    def _simplify(self, q, subject, chapter):

        return self._llm(f"""
Explain simply in 2–3 lines.
Stay on same topic.
NO LATEX.

Question: {q}
""")

    def _example(self, q, subject, chapter):

        return self._llm(f"""
Explain with a simple example or diagram description.
Stay on same topic.
NO LATEX.

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
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content

    def _is_smalltalk(self, q):
        return len(q.strip()) < 8

    # ================= ESCALATION =================
    def _escalate(self, q, s, c, sid):

        self.session_escalated[sid] = True

        try:
            self.lead_persistence.upsert_lead(
                session_id=sid,
                subject=s,
                chapter=c,
                question=q,
                escalation_code="ESC",
                escalation_reason="student_struggling",
                confidence=0.9,
                engagement_score=0,
                intent_strength=0.9,
                status="NEW"
            )
        except:
            pass

        return {
            "type": "escalation",
            "message": "This topic can be easier with personal guidance."
        }