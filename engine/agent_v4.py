import os
import re
from difflib import SequenceMatcher
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
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ================= AGENT =================
class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine):
        self.rag = rag_store
        self.session = session_engine

        self.client = OpenAI()
        self.cache = CacheEngine()
        self.logger = LoggingService()
        self.lead_persistence = LeadPersistenceService()

        self.session_confusion = {}
        self.session_escalated = {}
        self.session_last_q = {}

    # ================= SIMILAR =================
    def _similar(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    # ================= SMALL TALK =================
    def _is_small_talk(self, q):
        small = [
            "hi", "hello", "hey", "hellow",
            "haha", "lol", "good morning",
            "good evening"
        ]
        return q in small or len(q.split()) <= 2

    # ================= SUBJECT GUARD =================
    def _is_wrong_subject(self, q, chapter):
        if not chapter:
            return False

        keywords = {
            "electricity": ["current", "voltage", "resistance", "ohm"],
            "light": ["reflection", "refraction", "mirror", "lens"],
            "magnetic_effects_of_current": ["magnet", "field", "coil"],
            "work_power_energy": ["work", "energy", "power"]
        }

        for ch, words in keywords.items():
            if ch in chapter:
                if not any(w in q for w in words):
                    return True

        return False

    # ================= INTENT =================
    def _intent(self, q, sid):

        q = q.lower().strip()
        last_q = self.session_last_q.get(sid, "")

        # REPEAT DETECTION
        if last_q and self._similar(q, last_q) > 0.85:
            self.session_last_q[sid] = q
            return "CONFUSION"

        self.session_last_q[sid] = q

        # TEACHER INTENT
        if any(w in q for w in ["teacher", "help me", "talk to teacher"]):
            return "HELP"

        # FRUSTRATION
        if any(w in q for w in ["why repeating", "again same", "not helpful"]):
            return "FRUSTRATION"

        # CONFUSION
        if any(w in q for w in [
            "dont understand", "not understand",
            "confused", "explain again"
        ]):
            return "CONFUSION"

        if self._is_small_talk(q):
            return "SMALL_TALK"

        return "NORMAL"

    # ================= LLM RESPONSE =================
    def _llm_answer(self, question, context):

        prompt = f"""
You are a friendly school tutor.

Explain in:
- 2 to 3 lines max
- simple language
- 1 example

No "Definition / Key Idea" format.

Question: {question}
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )

        return res.choices[0].message.content.strip()

    # ================= MAIN =================
    def receive_question(self, question, context, session_id):

        sid = session_id
        q = question.lower()

        intent = self._intent(q, sid)

        if sid not in self.session_confusion:
            self.session_confusion[sid] = 0

        # SMALL TALK
        if intent == "SMALL_TALK":
            return {
                "type": "message",
                "message": "Hey 😊 Ask me anything from your chapter!"
            }

        # SUBJECT GUARD
        if self._is_wrong_subject(q, context.get("chapter", "")):
            return {
                "type": "message",
                "message": "This seems from another chapter. Please ask under the correct chapter 😊"
            }

        # HELP → ESCALATE
        if intent == "HELP":
            self.session_escalated[sid] = True

            try:
                self.lead_persistence.upsert_lead(
                    session_id=sid,
                    question=question,
                    subject=context.get("subject"),
                    chapter=context.get("chapter"),
                    escalation_reason="DIRECT_HELP"
                )
            except:
                pass

            return {
                "type": "escalation",
                "message": "I’ll connect you with a teacher for better help."
            }

        # FRUSTRATION
        if intent == "FRUSTRATION":
            self.session_confusion[sid] += 1

            if self.session_confusion[sid] >= 2:
                return {
                    "type": "escalation",
                    "message": "Looks like this needs personal guidance. Want me to connect you with a teacher?"
                }

            return {
                "type": "message",
                "message": "Got it 👍 Let me explain it in a simpler way."
            }

        # CONFUSION FLOW
        if intent == "CONFUSION":
            self.session_confusion[sid] += 1

            if self.session_confusion[sid] >= 3:
                self.session_escalated[sid] = True

                try:
                    self.lead_persistence.upsert_lead(
                        session_id=sid,
                        question=question,
                        subject=context.get("subject"),
                        chapter=context.get("chapter"),
                        escalation_reason="CONFUSION"
                    )
                except:
                    pass

                return {
                    "type": "escalation",
                    "message": "This topic may need personal guidance. Want to talk to a teacher?"
                }

        # CACHE
        cached = self.cache.lookup(question, context)
        if cached:
            return {
                "type": "message",
                "message": cached
            }

        # LLM
        answer = self._llm_answer(question, context)
        answer = clean(answer)

        self.cache.store(question, answer, context)

        return {
            "type": "message",
            "message": answer
        }