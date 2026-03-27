import re
from difflib import SequenceMatcher

from engine.cache_engine import CacheEngine
from engine.lead_persistence import LeadPersistenceService
from services.logging_service import LoggingService


class StudentSupportAgentV5:
    """Conversation layer tuned for teaching-first, lead-conversion-later behavior."""

    GREETING_WORDS = {"hi", "hello", "hey", "good morning", "good evening", "yo"}
    CONFUSION_HINTS = {"again", "confused", "not clear", "explain again", "didn't understand"}
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

    def _looks_like_basic_learning(self, q):
        q = (q or "").lower()
        starters = ("what is", "what are", "how does", "explain", "define", "tell me about")
        return q.startswith(starters) or "basics" in q or "basic" in q

    def _infer_intent(self, question, context, sid):
        q = (question or "").lower().strip()
        if not q:
            return {"intent": "learning", "needs_teacher": False, "confidence": 0.5, "reason": "empty"}

        if any(q.startswith(greet) for greet in self.GREETING_WORDS):
            return {"intent": "greeting", "needs_teacher": False, "confidence": 0.95, "reason": "greeting"}

        attempts = self.session_attempts.get(sid, 1)
        model_intent = self.rag.classify_intent(question, context, attempts=attempts)

        if self._looks_like_basic_learning(q) and attempts <= 2:
            model_intent["intent"] = "learning"
            model_intent["needs_teacher"] = False
            model_intent["reason"] = "teach_first_basic_query"

        # Safety fallback when classifier becomes uncertain.
        last_q = self.session_last_q.get(sid, "")
        repeated = bool(last_q) and self._similar(q, last_q) > 0.9
        self.session_last_q[sid] = q
        if repeated and not model_intent.get("needs_teacher"):
            model_intent["intent"] = "confusion"
            model_intent["reason"] = "repeat_detected"
        if any(h in q for h in self.CONFUSION_HINTS):
            model_intent["intent"] = "confusion"
        return model_intent

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

        if sid not in self.session_confusion:
            self.session_confusion[sid] = 0
        self.session_attempts[sid] = self.session_attempts.get(sid, 0) + 1

        if not question:
            return {
                "type": "message",
                "message": "Please ask your question in one line, and I will help step by step.",
            }

        intent_data = self._infer_intent(question, context, sid)
        intent = (intent_data.get("intent") or "learning").lower()
        needs_teacher = bool(intent_data.get("needs_teacher", False))
        confidence = float(intent_data.get("confidence", 0.6))
        reason = intent_data.get("reason", "model")

        if intent == "greeting":
            if context.get("unscoped"):
                return {
                    "type": "message",
                    "message": "Hi 👋 I’m ready to help. Ask any study query, exam concern, or guidance question.",
                }
            return {
                "type": "message",
                "message": "Hi 👋 Great to meet you. Ask me any concept from your selected chapter, and I’ll explain simply.",
            }

        if intent in {"learning", "confusion", "frustration", "help", "exam_support"}:
            self.session_last_learning_query[sid] = question

        if intent == "exam_support":
            self._persist_escalation_signal(
                sid,
                question,
                context,
                reason="Student asked for exam-performance guidance",
                code="EXAM_GUIDANCE",
                confidence=max(confidence, 0.8),
            )
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

        if intent == "help":
            self._persist_escalation_signal(
                sid,
                question,
                context,
                reason=f"Direct teacher request ({reason})",
                code="HELP_REQUEST",
                confidence=max(confidence, 0.9),
            )
            return {
                "type": "message",
                "teacher_offer": True,
                "message": "Absolutely — I can connect you to a teacher. Before that, do you want a quick simple explanation first?",
            }

        if intent == "frustration":
            self.session_confusion[sid] += 1
            if needs_teacher:
                self._persist_escalation_signal(
                    sid,
                    question,
                    context,
                    reason="Emotional urgency signal",
                    code="EMOTIONAL_SIGNAL",
                    confidence=max(confidence, 0.9),
                )
                return {
                    "type": "message",
                    "teacher_offer": True,
                    "message": (
                        "I hear you — this can feel stressful. I can connect you to an expert teacher whenever you want."
                    ),
                }

        if intent == "confusion":
            self.session_confusion[sid] += 1
            if self.session_confusion[sid] >= 3 or needs_teacher:
                self._persist_escalation_signal(
                    sid,
                    question,
                    context,
                    reason="Repeated confusion after multiple explanations",
                    code="REPEATED_CONFUSION",
                    confidence=max(confidence, 0.85),
                )
                return {
                    "type": "message",
                    "teacher_offer": True,
                    "message": "We have tried a few ways. Want me to connect you to an expert teacher for live help?",
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

            if intent == "confusion":
                answer = f"Let’s make it simpler: {answer}"
            elif intent == "frustration":
                answer = f"You’re doing fine — let’s go step by step. {answer}"

            if needs_teacher:
                answer = f"{answer} If helpful, I can also connect you with an expert teacher."

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
