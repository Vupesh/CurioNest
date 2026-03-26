import re
from difflib import SequenceMatcher

from engine.cache_engine import CacheEngine
from engine.lead_persistence import LeadPersistenceService
from services.logging_service import LoggingService


class StudentSupportAgentV5:
    """Conversation layer tuned for teaching-first, lead-conversion-later behavior."""

    HELP_WORDS = {
        "teacher", "mentor", "expert", "counsellor", "counselor", "call me",
        "connect me", "talk to teacher", "need teacher", "human support",
    }
    CONFUSION_WORDS = {
        "confused", "again", "repeat", "didn't understand", "dont understand",
        "not clear", "explain again", "can you re explain", "hard to understand",
    }
    FRUSTRATION_WORDS = {
        "not helpful", "useless", "frustrated", "annoyed", "stuck", "fed up",
    }
    EMOTIONAL_SIGNAL_WORDS = {
        "scared", "afraid", "anxious", "panic", "stressed", "urgent", "exam tomorrow",
        "failing", "i will fail", "crying", "pressure", "very worried",
    }

    def __init__(self, rag_store, session_engine):
        self.rag = rag_store
        self.session = session_engine
        self.cache = CacheEngine()
        self.logger = LoggingService()
        self.lead_persistence = LeadPersistenceService()

        self.session_confusion = {}
        self.session_last_q = {}
        self.session_attempts = {}

    def _similar(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    def _contains_any(self, text, phrases):
        return any(p in text for p in phrases)

    def _intent(self, q, sid):
        q = (q or "").lower().strip()
        if not q:
            return "LEARNING"

        last_q = self.session_last_q.get(sid, "")
        repeated_question = bool(last_q) and self._similar(q, last_q) > 0.88
        self.session_last_q[sid] = q

        if self._contains_any(q, self.HELP_WORDS):
            return "HELP"
        if self._contains_any(q, self.EMOTIONAL_SIGNAL_WORDS):
            return "FRUSTRATION"
        if repeated_question or self._contains_any(q, self.CONFUSION_WORDS):
            return "CONFUSION"
        if self._contains_any(q, self.FRUSTRATION_WORDS):
            return "FRUSTRATION"
        return "LEARNING"

    def _subject_in_scope(self, question, context):
        """Soft subject/chapter control: teach lightly, then redirect."""
        chapter = (context.get("chapter") or "").lower()
        if not chapter:
            return True

        tokenized = set(re.findall(r"[a-zA-Z_]+", question.lower()))
        chapter_tokens = set(chapter.replace("_", " ").split())

        # If no overlap with selected chapter terms, consider out-of-track.
        return len(tokenized.intersection(chapter_tokens)) > 0

    def _persist_escalation_signal(self, sid, question, context, reason, code, confidence):
        try:
            self.lead_persistence.upsert_lead(
                session_id=sid,
                subject=context.get("subject"),
                chapter=context.get("chapter"),
                question=question,
                escalation_code=code,
                escalation_reason=reason,
                confidence=confidence,
                engagement_score=0.7,
                intent_strength=confidence,
                status="new",
            )
        except Exception as exc:
            self.logger.log("LEAD_UPSERT_FAILED", str(exc))

    def receive_question(self, question, context, session_id):
        sid = session_id or "default"
        question = (question or "").strip()

        if sid not in self.session_confusion:
            self.session_confusion[sid] = 0
        self.session_attempts[sid] = self.session_attempts.get(sid, 0) + 1

        if not question:
            return {
                "type": "message",
                "message": "Please ask your question in one line, and I will help step by step.",
            }

        intent = self._intent(question, sid)

        if not self._subject_in_scope(question, context):
            return {
                "type": "message",
                "message": (
                    "This looks outside the selected chapter. Quick tip: switch chapter for exact help. "
                    "Please ask under correct subject > chapter"
                ),
            }

        if intent == "HELP":
            self._persist_escalation_signal(
                sid,
                question,
                context,
                reason="Direct teacher request",
                code="HELP_REQUEST",
                confidence=0.95,
            )
            return {
                "type": "escalation",
                "message": "Got it — I can connect you to a teacher now. Would you like that?",
            }

        if intent == "FRUSTRATION":
            self.session_confusion[sid] += 1
            if self._contains_any(question.lower(), self.EMOTIONAL_SIGNAL_WORDS):
                self._persist_escalation_signal(
                    sid,
                    question,
                    context,
                    reason="Emotional urgency signal",
                    code="EMOTIONAL_SIGNAL",
                    confidence=0.9,
                )
                return {
                    "type": "escalation",
                    "message": (
                        "I hear you — this feels stressful. I can connect you to a teacher for faster support."
                    ),
                }

        if intent == "CONFUSION":
            self.session_confusion[sid] += 1
            if self.session_confusion[sid] >= 3:
                self._persist_escalation_signal(
                    sid,
                    question,
                    context,
                    reason="Repeated confusion after multiple explanations",
                    code="REPEATED_CONFUSION",
                    confidence=0.88,
                )
                return {
                    "type": "escalation",
                    "message": "We tried a few times. Want me to connect you to a teacher for live help?",
                }

        try:
            cached = self.cache.lookup(question, context)
            if cached:
                return {"type": "message", "message": cached}
        except Exception as exc:
            self.logger.log("CACHE_LOOKUP_FAILED", str(exc))

        try:
            answer = self.rag.query(question, context)
            if not answer:
                self._persist_escalation_signal(
                    sid,
                    question,
                    context,
                    reason="Topic beyond syllabus context",
                    code="OUT_OF_SCOPE",
                    confidence=0.82,
                )
                return {
                    "type": "escalation",
                    "message": (
                        "I can teach basics, but this needs deeper support. Want to connect with a teacher?"
                    ),
                }

            if intent == "CONFUSION":
                answer = f"Let’s make it simpler: {answer}"
            elif intent == "FRUSTRATION":
                answer = f"You’re doing fine — let’s go step by step. {answer}"

            try:
                self.cache.store(question, answer, context)
            except Exception as exc:
                self.logger.log("CACHE_STORE_FAILED", str(exc))

            return {"type": "message", "message": answer}

        except Exception as exc:
            self.logger.log("RAG_QUERY_FAILED", str(exc))
            return {
                "type": "message",
                "message": (
                    "I’m still here. Please rephrase in one short line so I can explain it clearly."
                ),
            }
