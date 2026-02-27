import os
from openai import OpenAI
from services.logging_service import LoggingService
from budget_guard import check_and_update


class StudentSupportAgentV4:

    def __init__(self, rag_store):
        self.rag_store = rag_store
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.logger = LoggingService()

    # ================= ENTRY POINT =================

    def receive_question(self, question, context):

        try:
            identified = self.identify_context(question, context)
        except Exception:
            return self.escalate("Context identification failure", "ESC_CONTEXT_ERROR")

        if not identified or not isinstance(identified, dict):
            return self.escalate("Invalid context generated", "ESC_CONTEXT_INVALID")

        try:
            decision = self.decide_action(identified)
        except Exception:
            return self.escalate("Decision engine failure", "ESC_DECISION_FAILURE")

        if decision == "RESPOND":
            try:
                return self.respond(question, identified)
            except Exception:
                return self.escalate("Response generation failure", "ESC_RESPONSE_FAILURE")

        return self.escalate(
            identified.get("escalation_reason", "Unknown reason"),
            identified.get("escalation_code", "ESC_UNKNOWN")
        )

    # ================= CONTEXT =================

    def identify_context(self, question, context):

        try:
            subject = context.get("subject")
            chapter = context.get("chapter")
        except Exception:
            return None

        difficulty = self.detect_difficulty(question)

        return {
            "question": question,
            "subject": subject,
            "chapter": chapter,
            "difficulty": difficulty
        }

    # ================= DECISION =================

    def decide_action(self, identified):

        if identified["difficulty"] == "advanced":
            identified["escalation_reason"] = "Advanced question requires teacher"
            identified["escalation_code"] = "ESC_ADVANCED_TOPIC"

            self.logger.log("ESCALATION_EVENT", {
                "code": "ESC_ADVANCED_TOPIC",
                "subject": identified["subject"],
                "chapter": identified["chapter"]
            })

            return "ESCALATE"

        return "RESPOND"

    # ================= RESPONSE =================

    def respond(self, question, identified):

        chunks = self.rag_store.search(
            question,
            identified["subject"],
            identified["chapter"]
        )

        # --- No vectors or all rejected ---
        if not chunks:
            self.logger.log("ESCALATION_EVENT", {
                "code": "ESC_NO_VECTORS",
                "subject": identified["subject"],
                "chapter": identified["chapter"]
            })

            return self.escalate(
                "No reliable syllabus content found",
                "ESC_NO_VECTORS"
            )

        # --- Weak retrieval signal ---
        if len(chunks) < 2:
            self.logger.log("ESCALATION_EVENT", {
                "code": "ESC_LOW_CONFIDENCE",
                "subject": identified["subject"],
                "chapter": identified["chapter"]
            })

            return self.escalate(
                "Insufficient retrieval confidence",
                "ESC_LOW_CONFIDENCE"
            )

        try:
            return self.explain_with_ai(question, chunks)
        except Exception:
            return self.escalate(
                "AI explanation failure",
                "ESC_AI_FAILURE"
            )

    # ================= AI EXPLANATION =================

    def explain_with_ai(self, question, chunks):

        content = "\n".join(chunks)
        approx_tokens = len(content.split()) * 1.3

        # --- Context size guard ---
        if approx_tokens > 1200:
            self.logger.log("ESCALATION_EVENT", {
                "code": "ESC_CONTEXT_TOO_LARGE",
                "approx_tokens": approx_tokens
            })

            return self.escalate(
                "Context too large for safe processing",
                "ESC_CONTEXT_TOO_LARGE"
            )

        exceeded, reason = check_and_update(0)

        if exceeded:
            self.logger.log("ESCALATION_EVENT", {
                "code": "ESC_BUDGET_BLOCK",
                "reason": reason
            })

            return self.escalate(reason, "ESC_BUDGET_BLOCK")

        self.logger.log("OPENAI_REQUEST", {
            "model": "gpt-4o-mini"
        })

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=300,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a strictly retrieval-bound academic assistant. "
                            "Answer ONLY using the provided content. "
                            "If the content is insufficient, say exactly: "
                            "'Insufficient information in provided syllabus content.'"
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Content:\n{content}\n\nQuestion:\n{question}"
                    }
                ],
                timeout=8
            )

        except Exception as e:
            self.logger.log("ESCALATION_EVENT", {
                "code": "ESC_AI_TIMEOUT",
                "error": str(e)
            })

            return self.escalate(
                "AI provider failure",
                "ESC_AI_TIMEOUT"
            )

        try:
            usage = response.usage

            if usage:
                self.logger.log("OPENAI_USAGE", {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens
                })

                check_and_update(usage.total_tokens)

        except Exception:
            pass

        try:
            answer = response.choices[0].message.content

            if not answer:
                return self.escalate(
                    "Empty AI response",
                    "ESC_EMPTY_RESPONSE"
                )

            if "Insufficient information" in answer:
                self.logger.log("ESCALATION_EVENT", {
                    "code": "ESC_KNOWLEDGE_GAP"
                })

                return self.escalate(
                    "Knowledge base lacks required explanation",
                    "ESC_KNOWLEDGE_GAP"
                )

            return answer

        except Exception as e:
            self.logger.log("ESCALATION_EVENT", {
                "code": "ESC_AI_PARSE_FAILURE",
                "error": str(e)
            })

            return self.escalate(
                "AI response failure",
                "ESC_AI_PARSE_FAILURE"
            )

    # ================= ESCALATION =================

    def escalate(self, reason, code):
        self.logger.log("ESCALATION_TRIGGERED", {
            "code": code,
            "reason": reason
        })
        return f"ESCALATE TO SME: {reason}"

    # ================= DIFFICULTY =================

    def detect_difficulty(self, question):

        for k in ["prove", "derive", "theorem"]:
            if k in question.lower():
                return "advanced"

        return "basic"