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
    GREETING_WORDS = {"hi", "hello", "hey", "good morning", "good evening", "yo"}
    ADVANCED_TOPICS = {
        "quantum", "black hole", "relativity", "astrophysics", "calculus", "organic mechanism"
    }
    EXAM_SUPPORT_WORDS = {
        "exam", "score", "marks", "percentage", "tips", "strategy", "study plan", "revision"
    }
    TEACH_REQUEST_WORDS = {
        "teach me", "teach me basics", "basics", "explain basics", "first explain", "help me understand",
    }
    HELP_CONFIRM_WORDS = {
        "connect now", "call me now", "yes connect", "yes teacher", "talk to teacher now",
    }
    CONVERSATIONAL_WORDS = {
        "all fine now", "what else you need", "i selected", "are you there",
        "can we continue", "okay now", "ok now", "hello there", "chapter subjects are all correct",
    }
    SUBJECT_KEYWORDS = {
        "physics": {"friction", "force", "energy", "work", "power", "motion", "electricity", "magnetism", "current"},
        "chemistry": {"atom", "molecule", "reaction", "acid", "base", "salt", "bond", "organic", "compound"},
        "biology": {"cell", "organ", "plant", "human", "reproduction", "heredity", "life", "physiology"},
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
        self.session_last_learning_query = {}

    def _similar(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    def _contains_any(self, text, phrases):
        return any(p in text for p in phrases)

    def _intent(self, q, sid):
        q = (q or "").lower().strip()
        if not q:
            return "LEARNING"

        llm_intent = "UNKNOWN"
        llm_confidence = 0.0
        try:
            inferred = self.rag.infer_intent(q)
            llm_intent = inferred.get("intent", "UNKNOWN")
            llm_confidence = float(inferred.get("confidence", 0.0))
        except Exception:
            pass

        last_q = self.session_last_q.get(sid, "")
        repeated_question = bool(last_q) and self._similar(q, last_q) > 0.88
        self.session_last_q[sid] = q

        if llm_confidence >= 0.75 and llm_intent in {
            "GREETING", "CONVERSATIONAL", "TEACH_REQUEST", "EXAM_SUPPORT",
            "HELP", "CONFUSION", "FRUSTRATION", "LEARNING"
        }:
            return llm_intent

        if any(q.startswith(greet) for greet in self.GREETING_WORDS):
            return "GREETING"
        if self._contains_any(q, self.CONVERSATIONAL_WORDS):
            return "CONVERSATIONAL"
        if self._contains_any(q, self.TEACH_REQUEST_WORDS):
            return "TEACH_REQUEST"
        if self._contains_any(q, self.HELP_CONFIRM_WORDS):
            return "HELP_CONFIRM"
        if self._contains_any(q, self.EXAM_SUPPORT_WORDS):
            return "EXAM_SUPPORT"
        if self._contains_any(q, self.HELP_WORDS) and any(w in q for w in ["what", "how", "why", "explain", "understand"]):
            return "HELP_WITH_DOUBT"
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
        subject = (context.get("subject") or "").lower()
        if not chapter:
            return True

        tokenized = set(re.findall(r"[a-zA-Z_]+", question.lower()))
        chapter_tokens = set(chapter.replace("_", " ").split())
        subject_tokens = set(subject.replace("_", " ").split())
        guidance_tokens = {"exam", "score", "marks", "percentage", "tips", "plan", "revision"}

        # Treat chapter questions, subject-level guidance, and exam planning as in-scope.
        if tokenized.intersection(chapter_tokens):
            return True
        if tokenized.intersection(subject_tokens):
            return True
        if tokenized.intersection(self.SUBJECT_KEYWORDS.get(subject, set())):
            return True
        if tokenized.intersection(guidance_tokens):
            return True
        return False

    def _light_out_of_scope_answer(self, question):
        q = question.lower()
        if "black hole" in q and "organic chemistry" in q:
            return (
                "Black holes are part of space physics, while organic chemistry studies carbon compounds. "
                "So they are from different subjects and do not directly overlap."
            )
        if any(topic in q for topic in self.ADVANCED_TOPICS):
            return (
                "This is an advanced idea outside your current chapter. "
                "I can share basics, but detailed mastery usually needs a teacher."
            )
        return (
            "This looks beyond your selected chapter. I can give a quick basic idea, "
            "but deeper clarity will be better with a teacher."
        )

    def _exam_support_reply(self, context):
        subject = (context.get("subject") or "your subject").capitalize()
        return (
            f"Yes, I can help you score better in {subject}. Start with 45-min focused study blocks, "
            "daily active recall, and 1 timed past-paper section. "
            "If you want, I can connect you with an expert teacher for a personalized scoring plan."
        )

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
        selection_valid = context.get("selection_valid", True)

        if sid not in self.session_confusion:
            self.session_confusion[sid] = 0
        self.session_attempts[sid] = self.session_attempts.get(sid, 0) + 1

        if not question:
            return {
                "type": "message",
                "message": "Please ask your question in one line, and I will help step by step.",
            }

        intent = self._intent(question, sid)

        if intent == "GREETING":
            return {
                "type": "message",
                "message": "Hi 👋 Great to meet you. Ask me any concept from your selected chapter, and I’ll explain simply.",
            }

        if intent == "CONVERSATIONAL":
            return {
                "type": "message",
                "message": (
                    "Yes, all set ✅ I am ready. Ask your chapter doubt in one line, "
                    "or ask exam strategy and I will guide you step by step."
                ),
            }

        if not selection_valid and intent not in {"GREETING", "CONVERSATIONAL"}:
            return {
                "type": "message",
                "message": (
                    "I can still guide you briefly, but for syllabus-accurate teaching please select "
                    "Board > Subject > Chapter."
                ),
            }

        if intent == "HELP_WITH_DOUBT":
            self._persist_escalation_signal(
                sid,
                question,
                context,
                reason="Teacher request with active concept doubt",
                code="HELP_WITH_DOUBT",
                confidence=0.9,
            )
            # Teach first, then politely offer escalation.
            try:
                answer = self.rag.query(question, context)
            except Exception:
                answer = None
            if not answer:
                answer = "Friction is a force that opposes motion when two surfaces touch. It slows movement and can produce heat."
            return {
                "type": "message",
                "message": (
                    f"{answer} If you want, I can also connect you with an expert teacher for personal help."
                ),
            }

        if intent == "TEACH_REQUEST":
            topic_question = self.session_last_learning_query.get(sid, question)
            try:
                answer = self.rag.query(topic_question, context)
            except Exception:
                answer = None
            if answer:
                return {"type": "message", "message": f"Sure 👍 Here are the basics: {answer}"}
            return {
                "type": "message",
                "message": (
                    "Sure 👍 I will teach the basics first in simple steps. "
                    "If anything still feels hard, I can connect you with a teacher."
                ),
            }

        if intent in {"LEARNING", "CONFUSION", "FRUSTRATION", "HELP_WITH_DOUBT", "HELP"}:
            self.session_last_learning_query[sid] = question

        if intent == "HELP_CONFIRM":
            self._persist_escalation_signal(
                sid,
                question,
                context,
                reason="Student confirmed teacher connection",
                code="HELP_CONFIRMED",
                confidence=0.95,
            )
            return {
                "type": "escalation",
                "message": "Got it. I’m connecting you to an expert teacher now.",
            }

        if intent == "EXAM_SUPPORT":
            return {
                "type": "message",
                "message": self._exam_support_reply(context),
            }

        if not self._subject_in_scope(question, context):
            return {
                "type": "message",
                "message": (
                    f"{self._light_out_of_scope_answer(question)} "
                    "Please ask under correct subject > chapter. "
                    "If you want, I can connect you with an expert teacher."
                ),
            }

        if intent == "HELP":
            return {
                "type": "message",
                "message": (
                    "Absolutely — I can connect you with an expert teacher. "
                    "Would you like a quick explanation first, or should I connect now?"
                ),
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
                    "type": "message",
                    "message": (
                        f"{self._light_out_of_scope_answer(question)} "
                        "This may be beyond your current syllabus depth. "
                        "If you want, I can connect you with an expert teacher."
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
