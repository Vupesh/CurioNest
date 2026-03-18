import os
import json
import re
from typing import Dict, Any, List

from openai import OpenAI

from services.logging_service import LoggingService
from engine.cache_engine import CacheEngine
from engine.lead_persistence import LeadPersistenceService


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

CLASSIFICATION_MAX_TOKENS = 150
ANSWER_MAX_TOKENS = 1000


def normalize_latex(text: str):

    if not text:
        return text

    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text)
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text)

    text = re.sub(r"\n\s*\n", "\n\n", text)

    return text.strip()


def safe_json_parse(content: str, default):

    try:

        cleaned = re.sub(r"^```json", "", content.strip())
        cleaned = re.sub(r"```$", "", cleaned)

        return json.loads(cleaned)

    except Exception:
        return default


class StudentSupportAgentV5:

    def __init__(self, rag_store, session_engine=None):

        self.rag_store = rag_store
        self.session_engine = session_engine

        self.logger = LoggingService()

        self.cache = CacheEngine()

        self.lead_persistence = LeadPersistenceService()

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # =====================================================
    # ENTRY POINT
    # =====================================================

    def receive_question(self, question: str, context: Dict[str, str], session_id: str):

        subject = context.get("subject")
        chapter = context.get("chapter")

        # ---------------------------------------------------
        # 1 CACHE CHECK
        # ---------------------------------------------------

        cached = self.cache.search_cache(question, subject)

        if cached:

            self.logger.log("CACHE_HIT", question[:80])

            return {
                "type": "answer",
                "message": cached
            }

        # ---------------------------------------------------
        # 2 QUESTION ANALYSIS
        # ---------------------------------------------------

        analysis = self.analyze_question(question)

        intent = analysis["intent"]
        difficulty = analysis["difficulty"]

        # ---------------------------------------------------
        # 3 RAG SEARCH
        # ---------------------------------------------------

        chunks = self.rag_store.search(question, subject, chapter)

        coverage = len(chunks)

        # ---------------------------------------------------
        # 4 DECISION ENGINE
        # ---------------------------------------------------

        if coverage == 0:

            if intent in ["HELP_REQUEST", "CONFUSION"]:

                return self.escalate(question, subject, chapter, session_id)

        # ---------------------------------------------------
        # 5 GENERATE ANSWER
        # ---------------------------------------------------

        if coverage > 0:

            answer = self.answer_with_context(question, chunks)

        else:

            answer = self.answer_general(question)

        # ---------------------------------------------------
        # 6 STORE CACHE
        # ---------------------------------------------------

        try:

            self.cache.store_cache(question, answer, subject, chapter)

        except Exception as e:

            self.logger.log("CACHE_STORE_FAIL", str(e))

        return {
            "type": "answer",
            "message": answer
        }

    # =====================================================
    # QUESTION ANALYSIS
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

            data = safe_json_parse(res.choices[0].message.content, default)

            return data

        except Exception:

            return default

    # =====================================================
    # RAG ANSWER
    # =====================================================

    def answer_with_context(self, question: str, chunks: List[str]):

        context_text = "\n\n".join(chunks)

        prompt = f"""
Use ONLY the syllabus context.

Context:
{context_text}

Student Question:
{question}

Explain in simple exam ready format.

Structure:

Concept
Formula
Example
"""

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=ANSWER_MAX_TOKENS,
            temperature=0.3,
            messages=[
                {"role": "system", "content": "You are a helpful school tutor"},
                {"role": "user", "content": prompt}
            ]
        )

        return normalize_latex(res.choices[0].message.content)

    # =====================================================
    # FALLBACK
    # =====================================================

    def answer_general(self, question: str):

        res = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=ANSWER_MAX_TOKENS,
            temperature=0.3,
            messages=[
                {"role": "system", "content": "You are a helpful tutor"},
                {"role": "user", "content": question}
            ]
        )

        return normalize_latex(res.choices[0].message.content)

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
            escalation_reason="Student needs human help",
            confidence=0.7,
            engagement_score=0,
            intent_strength=0.7,
            status="NEW"
        )

        return {
            "type": "escalation",
            "message": "A teacher can help you with this question."
        }