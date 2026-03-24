import os
import re
from difflib import SequenceMatcher

from engine.cache_engine import CacheEngine
from services.logging_service import LoggingService
from engine.lead_persistence import LeadPersistenceService

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def clean(text):
    if not text:
        return text
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine):
        self.rag = rag_store
        self.session = session_engine

        self.cache = CacheEngine()
        self.logger = LoggingService()
        self.lead_persistence = LeadPersistenceService()

        self.session_confusion = {}
        self.session_last_q = {}

    # ---------------- SIMILAR ----------------
    def _similar(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    # ---------------- INTENT ----------------
    def _intent(self, q, sid):

        q = q.lower().strip()
        last_q = self.session_last_q.get(sid, "")

        if last_q and self._similar(q, last_q) > 0.85:
            self.session_last_q[sid] = q
            return "CONFUSION"

        self.session_last_q[sid] = q

        if any(w in q for w in ["teacher", "help me"]):
            return "HELP"

        if any(w in q for w in ["confused", "dont understand", "again"]):
            return "CONFUSION"

        if any(w in q for w in ["why", "not helpful"]):
            return "FRUSTRATION"

        if len(q.split()) <= 2:
            return "SMALL_TALK"

        return "NORMAL"

    # ---------------- SUBJECT GUARD (SMART) ----------------
    def _subject_score(self, q, chapter):

        keywords = {
            "electricity": ["electricity", "current", "voltage", "resistance"],
            "acid_bases_salts": ["acid", "base", "salt", "ph", "alkaline"],
            "heredity": ["gene", "dna", "inherit"],
        }

        for ch, words in keywords.items():
            if ch in chapter:
                score = sum([1 for w in words if w in q])
                return score

        return 1  # allow by default

    # ---------------- MAIN ----------------
    def receive_question(self, question, context, session_id):

        sid = session_id
        q = question.lower()

        intent = self._intent(q, sid)

        if sid not in self.session_confusion:
            self.session_confusion[sid] = 0

        # SMALL TALK
        if intent == "SMALL_TALK":
            return {"type": "message", "message": "Hey 😊 Ask me anything!"}

        # SUBJECT CHECK (SMART, NOT BLOCKING)
        score = self._subject_score(q, context.get("chapter", ""))

        if score == 0:
            return {
                "type": "message",
                "message": "This seems from another chapter. Please switch subject 😊"
            }

        # HELP
        if intent == "HELP":
            self.lead_persistence.upsert_lead(
                session_id=sid,
                question=question,
                subject=context.get("subject"),
                chapter=context.get("chapter"),
                escalation_reason="HELP"
            )
            return {"type": "escalation", "message": "Connecting you to a teacher."}

        # CONFUSION
        if intent == "CONFUSION":
            self.session_confusion[sid] += 1

            if self.session_confusion[sid] >= 3:
                return {
                    "type": "escalation",
                    "message": "This needs teacher help. Want me to connect you?"
                }

        # CACHE
        try:
            cached = self.cache.lookup(question, context)
            if cached:
                return {"type": "message", "message": cached}
        except:
            pass

        # RAG (SAFE)
        try:
            answer = self.rag.query(question, context)

            if not answer:
                return {
                    "type": "escalation",
                    "message": "This needs deeper help. Want a teacher?"
                }

            answer = clean(answer)

        except:
            return {
                "type": "escalation",
                "message": "This is a bit advanced. Want teacher help?"
            }

        # STORE CACHE
        try:
            self.cache.store(question, answer, context)
        except:
            pass

        return {"type": "message", "message": answer}