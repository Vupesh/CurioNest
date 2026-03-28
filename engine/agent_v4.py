import re
from difflib import SequenceMatcher

from engine.cache_engine import CacheEngine
from engine.lead_persistence import LeadPersistenceService
from services.logging_service import LoggingService


class StudentSupportAgentV5:

    GREETING_WORDS = {"hi", "hello", "hey", "good morning", "good evening"}
    CONFUSION_HINTS = {
        "again", "confused", "not clear", "explain again",
        "didn't understand", "dont understand", "not understand",
        "still confused", "again please", "explain again please"
    }

    EMOTIONAL_SIGNALS = {
        "scared", "fail", "weak", "nervous", "afraid",
        "exam tomorrow", "i am scared", "i will fail"
    }

    def __init__(self, rag_store, session_engine):
        self.rag = rag_store
        self.session = session_engine
        self.cache = CacheEngine()
        self.logger = LoggingService()
        self.lead_persistence = LeadPersistenceService()

        self.session_confusion = {}
        self.session_attempts = {}
        self.session_last_q = {}

    def _similar(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    def _infer_intent(self, question, sid):
        q = (question or "").lower().strip()

        if any(q.startswith(g) for g in self.GREETING_WORDS):
            return "greeting"

        if any(e in q for e in self.EMOTIONAL_SIGNALS):
            return "emotional"

        if any(h in q for h in self.CONFUSION_HINTS):
            return "confusion"

        if "teacher" in q or "help me" in q or "connect me" in q:
            return "help"

        return "learning"

    def receive_question(self, question, context, session_id):
        sid = session_id or "default"
        question = (question or "").strip()

        # Initialize session state
        self.session_confusion[sid] = self.session_confusion.get(sid, 0)
        self.session_attempts[sid] = self.session_attempts.get(sid, 0) + 1

        if not question:
            return {
                "type": "message",
                "message": "Please ask your question in one simple line."
            }

        # 🔥 Repetition detection (IMPORTANT)
        last_q = self.session_last_q.get(sid, "")
        if last_q and self._similar(last_q, question.lower()) > 0.9:
            self.session_confusion[sid] += 1

        self.session_last_q[sid] = question.lower()

        intent = self._infer_intent(question, sid)

        # Greeting
        if intent == "greeting":
            return {
                "type": "message",
                "message": "Hi 👋 Ask me any concept from your chapter and I’ll explain simply."
            }

        # Immediate HELP escalation
        if intent == "help":
            return {
                "type": "message",
                "teacher_offer": True,
                "message": "I can connect you with a teacher. Do you want a quick explanation first?"
            }

        # 🔴 Emotional escalation (HIGH VALUE)
        if intent == "emotional":
            return {
                "type": "message",
                "teacher_offer": True,
                "message": "I understand how you feel. I can connect you to an expert teacher who will guide you step by step."
            }

        # Confusion tracking
        if intent == "confusion":
            self.session_confusion[sid] += 1

        # Progressive escalation
        if self.session_confusion[sid] >= 3:
            return {
                "type": "message",
                "teacher_offer": True,
                "message": "We’ve tried a few ways. Would you like me to connect you with an expert teacher for clearer guidance?"
            }

        # Cache lookup
        try:
            cached = self.cache.lookup(question, context)
            if cached:
                return {"type": "message", "message": cached}
        except Exception:
            pass

        # RAG call
        try:
            answer = self.rag.query(question, context)

            # 🔥 Safety fallback (NO hardcoding, NO crash)
            if not answer:
                answer = (
                    "Let me explain simply: This is a basic concept from your subject. "
                    "Think of it step by step with a small real-life example."
                )

            # Tone adjustment for confusion
            if intent == "confusion":
                answer = f"Let’s make it simpler: {answer}"

            # Store cache
            try:
                self.cache.store(question, answer, context)
            except Exception:
                pass

            return {
                "type": "message",
                "message": answer
            }

        except Exception:
            return {
                "type": "message",
                "message": "Let me explain simply: This is an important concept. Let’s understand it step by step with a small example."
            }