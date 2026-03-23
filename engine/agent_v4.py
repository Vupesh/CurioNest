import os
import re
from difflib import SequenceMatcher
from openai import OpenAI

from engine.cache_engine import CacheEngine
from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def clean(text):
    if not text:
        return text

    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text)
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text)
    text = re.sub(r"\\frac\{(.*?)\}\{(.*?)\}", r"\1/\2", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


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

    # ================= SIMILARITY =================
    def _similar(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    # ================= INTENT =================
    def _intent(self, q, sid):

        q = q.lower().strip()
        last_q = self.session_last_q.get(sid, "")

        # ✅ REPEAT DETECTION
        if last_q and self._similar(q, last_q) > 0.85:
            self.session_last_q[sid] = q
            return "CONFUSION"

        self.session_last_q[sid] = q

        # HELP
        if any(w in q for w in ["teacher", "help me", "talk to teacher"]):
            return "HELP"

        # CONFUSION WORDS
        if any(w in q for w in [
            "dont understand", "not understand",
            "confused", "explain again"
        ]):
            return "CONFUSION"

        # SMALL TALK
        if len(q.split()) <= 2:
            return "SMALL_TALK"

        return "NORMAL"

    # ================= MAIN =================
    def receive_question(self, question, context, session_id):

        sid = session_id
        intent = self._intent(question, sid)

        if sid not in self.session_confusion:
            self.session_confusion[sid] = 0

        # SMALL TALK
        if intent == "SMALL_TALK":
            return {
                "type": "message",
                "message": "Ask me anything from your chapter 😊"
            }

        # HELP → ESCALATE
        if intent == "HELP":
            self.session_escalated[sid] = True
            return {
                "type": "escalation",
                "message": "Let me connect you with a teacher."
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
                    "message": "It seems this topic needs personal guidance."
                }

        # ================= CACHE =================
        cached = self.cache.lookup(question, context)
        if cached:
            return {
                "type": "message",
                "message": cached
            }

        # ================= RAG =================
        answer = self.rag.query(question, context)

        answer = clean(answer)

        self.cache.store(question, answer, context)

        return {
            "type": "message",
            "message": answer
        }