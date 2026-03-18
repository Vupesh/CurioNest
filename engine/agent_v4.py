import os
import json
import re
from typing import Dict, Any, List

from openai import OpenAI

from services.logging_service import LoggingService
from engine.cache_engine import CacheEngine
from engine.query_guardrail import QueryGuardrail
from engine.lead_persistence import LeadPersistenceService


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

CLASSIFICATION_MAX_TOKENS = 150
ANSWER_MAX_TOKENS = 1000


# ==========================================================
# LATEX NORMALIZATION
# ==========================================================

def normalize_latex(text: str):

    if not text:
        return text

    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text)
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text)

    text = re.sub(r"\n\s*\n", "\n\n", text)

    return text.strip()


# ==========================================================
# SAFE JSON PARSER
# ==========================================================

def safe_json_parse(content: str, default):

    try:

        cleaned = re.sub(r"^```json", "", content.strip())
        cleaned = re.sub(r"```$", "", cleaned)

        return json.loads(cleaned)

    except Exception:
        return default


# ==========================================================
# AGENT
# ==========================================================

class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine=None):

        self.rag_store = rag_store
        self.session_engine = session_engine

        self.logger = LoggingService()

        self.cache = CacheEngine()

        self.guardrail = QueryGuardrail()

        self.lead_persistence = LeadPersistenceService()

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # =====================================================
    # MAIN ENTRY
    # =====================================================

    def receive_question(self, question: str, context: Dict[str, str], session_id: str):

        subject = context.get("subject")
        chapter = context.get("chapter")

        # --------------------------------------------
        # 1 GUARDRAIL
        # --------------------------------------------

        guard = self.guardrail.check(question)

        if guard:

            if guard["type"] == "smalltalk":

                return {
                    "type": "answer",
                    "message": guard["message"]
                }

            if guard["type"] == "ignore":

                return {
                    "type": "answer",
                    "message": "Please ask a clear academic question."
                }

        # --------------------------------------------
        # 2 CACHE
        # --------------------------------------------

        cached = self.cache.search_cache(question, subject)

        if cached:

            self.logger.log("CACHE_HIT", question[:80])

            return {
                "type": "answer",
                "message": cached
            }

        # --------------------------------------------
        # 3 MEMORY
        # --------------------------------------------

        conversation_history = []

        if self.session_engine:

            conversation_history = self.session_engine.get_recent_messages(
                session_id,
                limit=6
            )

            self.session_engine.store_message(
                session_id,
                "user",
                question
            )

        # --------------------------------------------
        # 4 AI INTENT ANALYSIS
        # --------------------------------------------

        analysis = self.analyze_question(question)

        intent = analysis["intent"]
        difficulty = analysis["difficulty"]

        # --------------------------------------------
        # 5 RAG SEARCH
        # --------------------------------------------

        chunks = self.rag_store.search(question, subject, chapter)

        coverage = len(chunks)

        # --------------------------------------------
        # 6 ESCALATION DECISION
        # --------------------------------------------

        if coverage == 0 and intent in ["HELP_REQUEST", "CONFUSION"]:

            return self.escalate(
                question,
                subject,
                chapter,
                session_id
            )

        # --------------------------------------------
        # 7 ANSWER GENERATION
        # --------------------------------------------

        if coverage > 0:

            answer = self.answer_with_context(
                question,
                chunks,
                conversation_history
            )

        else:

            answer = self.answer_general(
                question,
                conversation_history
            )

        # --------------------------------------------
        # 8 STORE CACHE
        # --------------------------------------------

        try:

            self.cache.store_cache(
                question,
                answer,
                subject,
                chapter
            )

        except Exception as e:

            self.logger.log("CACHE_STORE_FAIL", str(e))

        # --------------------------------------------
        # 9 SAVE MEMORY
        # --------------------------------------------

        if self.session_engine:

            self.session_engine.store_message(
                session_id,
                "assistant",
                answer
            )

        return {
            "type": "answer",
            "message": answer
        }

    # =====================================================
    # AI QUESTION ANALYSIS
    # =====================================================

    def analyze_question(self, question: str):

        prompt = f"""
Analyze the student question.

Return JSON.

intent:
["CONCEPT_LEARNING","CONFUSION","HELP_REQUEST","ADVANCED_TOPIC","GENERAL"]

difficulty:
["BASIC","INTERMEDIATE","ADVANCED"]

Question:
{question}
"""

        default = {
            "intent": "CONCEPT_LEARNING",
            "difficulty": "BASIC"
        }

        try:

            res = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                max_tokens=CLASSIFICATION_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": "Return JSON only"},
                    {"role": "user", "content": prompt}
                ]
            )

            data = safe_json_parse(
                res.choices[0].message.content,
                default
            )

            return data

        except Exception:

            return default

    # =====================================================
    # RAG ANSWER
    # =====================================================

    def answer_with_context(self, question, chunks, history):

        context_text = "\n\n".join(chunks)

        messages = [
            {"role": "system", "content": "You are a helpful school tutor"}
        ]

        messages.extend(history)

        prompt = f"""
Use ONLY the syllabus context.

Context:
{context_text}

Student Question:
{question}

Explain in exam ready format.

Structure:

Concept
Formula
Example
"""

        messages.append({
            "role": "user",
            "content": prompt
        })

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=ANSWER_MAX_TOKENS,
            temperature=0.3,
            messages=messages
        )

        return normalize_latex(
            res.choices[0].message.content
        )

    # =====================================================
    # GENERAL ANSWER
    # =====================================================

    def answer_general(self, question, history):

        messages = [
            {"role": "system", "content": "You are a helpful tutor"}
        ]

        messages.extend(history)

        messages.append({
            "role": "user",
            "content": question
        })

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=ANSWER_MAX_TOKENS,
            temperature=0.3,
            messages=messages
        )

        return normalize_latex(
            res.choices[0].message.content
        )

    # =====================================================
    # ESCALATION
    # =====================================================

    def escalate(self, question, subject, chapter, session_id):

        self.lead_persistence.upsert_lead(
            session_id=session_id,
            subject=subject,
            chapter=chapter,
            question=question,
            escalation_code="ESC_LEARNING_SUPPORT",
            escalation_reason="Student requires expert help",
            confidence=0.7,
            engagement_score=0,
            intent_strength=0.7,
            status="NEW"
        )

        return {
            "type": "escalation",
            "message": "A teacher can help you with this question."
        }