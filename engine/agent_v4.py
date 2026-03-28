import re
from difflib import SequenceMatcher

from engine.cache_engine import CacheEngine
from engine.lead_persistence import LeadPersistenceService
from services.logging_service import LoggingService
from engine.lead_engine import LeadEngine
from engine.ux_lead_engine import UXLeadEngine


class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine):
        self.rag = rag_store
        self.session = session_engine
        self.cache = CacheEngine()
        self.logger = LoggingService()
        self.lead_persistence = LeadPersistenceService()

        self.lead_engine = LeadEngine()
        self.ux_lead_engine = UXLeadEngine()

        self.session_confusion = {}
        self.session_attempts = {}

    def receive_question(self, question, context, session_id):

        sid = session_id or "default"
        question = (question or "").strip()

        self.session_confusion[sid] = self.session_confusion.get(sid, 0)
        self.session_attempts[sid] = self.session_attempts.get(sid, 0) + 1

        if not question:
            return {"type": "message", "message": "Please ask your question clearly."}

        # 🔥 AI-based intent classification
        intent_data = self.rag.classify_intent(
            question,
            context,
            attempts=self.session_attempts[sid]
        )

        intent = intent_data["intent"]
        confidence = intent_data["confidence"]
        needs_teacher = intent_data["needs_teacher"]

        # 🔴 Immediate escalation (AI decides)
        if needs_teacher and intent in ["help", "frustration"]:
            return {
                "type": "message",
                "teacher_offer": True,
                "message": "I understand your situation. A teacher can guide you better. Would you like to connect?"
            }

        # 🟡 Confusion tracking (AI + attempts)
        if intent == "confusion":
            self.session_confusion[sid] += 1

        if self.session_confusion[sid] >= 3:
            return {
                "type": "message",
                "teacher_offer": True,
                "message": "It seems this needs deeper guidance. Would you like help from a teacher?"
            }

        # Cache
        try:
            cached = self.cache.lookup(question, context)
            if cached:
                return {"type": "message", "message": cached}
        except:
            pass

        # RAG Answer
        try:
            answer = self.rag.query(question, context)

            if not answer:
                answer = "Let me explain simply: This concept can be understood step by step with a simple example."

            # 🔥 AI-driven escalation scoring (NO hardcoding)
            escalation_confidence = int(confidence * 40)
            engagement_score = min(self.session_attempts[sid] * 5, 20)
            intent_strength = int(confidence * 3)

            # UX trigger
            should_prompt = self.ux_lead_engine.evaluate(
                sid,
                escalation_confidence,
                engagement_score
            )

            # Lead qualification
            self.lead_engine.evaluate_lead(
                session_id=sid,
                subject=context.get("subject"),
                chapter=context.get("chapter"),
                escalation_code=intent.upper(),
                escalation_reason=intent_data.get("reason"),
                escalation_confidence=escalation_confidence,
                engagement_score=engagement_score,
                intent_strength=intent_strength
            )

            # Cache store
            try:
                self.cache.store(question, answer, context)
            except:
                pass

            return {
                "type": "message",
                "message": answer,
                "teacher_offer": should_prompt
            }

        except Exception:
            return {
                "type": "message",
                "message": "Let me explain simply: This is an important concept. Let's understand it step by step."
            }