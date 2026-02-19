import os
from openai import OpenAI
from services.logging_service import LoggingService
from budget_guard import check_and_update


class StudentSupportAgentV4:
    def __init__(self, rag_store):
        self.rag_store = rag_store
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.logger = LoggingService()

    def receive_question(self, question, context):

        try:
            identified = self.identify_context(question, context)
        except Exception:
            return "ESCALATE TO SME: Context identification failure"

        if not identified or not isinstance(identified, dict):
            return "ESCALATE TO SME: Invalid context generated"

        try:
            decision = self.decide_action(identified)
        except Exception:
            return "ESCALATE TO SME: Decision engine failure"

        if decision == "RESPOND":
            try:
                return self.respond(question, identified)
            except Exception:
                return "ESCALATE TO SME: Response generation failure"

        return self.escalate(identified.get("escalation_reason", "Unknown reason"))

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

    def decide_action(self, identified):
        if identified["difficulty"] == "advanced":
            identified["escalation_reason"] = "Advanced question requires teacher"
            return "ESCALATE"
        return "RESPOND"

    def respond(self, question, identified):

        chunks = self.rag_store.search(
            question,
            identified["subject"],
            identified["chapter"]
        )

        if not chunks:
            return self.escalate("No syllabus content found")

        if len(chunks) < 2:
            return self.escalate("Insufficient retrieval confidence")

        try:
            return self.explain_with_ai(question, chunks)
        except Exception:
            return self.escalate("AI explanation failure")

    def explain_with_ai(self, question, chunks):

        content = "\n".join(chunks)

        # ✅ Context Size Kill-Switch (Per-Request Cost Safety)
        approx_tokens = len(content.split()) * 1.3

        if approx_tokens > 1200:
            self.logger.log("OPENAI_COST_BLOCKED", {
                "approx_tokens": approx_tokens
            })
            return self.escalate("Context too large for safe processing")

        # ✅ Atomic Budget Check (Race-Condition Safe)
        exceeded, reason = check_and_update(0)
        if exceeded:
            self.logger.log("BUDGET_BLOCKED", reason)
            return self.escalate(reason)

        self.logger.log("OPENAI_REQUEST", {
            "model": "gpt-4o-mini"
        })

        self.logger.log("OPENAI_GUARDRAIL", {
            "max_tokens": 300
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
            self.logger.log("OPENAI_TIMEOUT_OR_FAILURE", str(e))
            return self.escalate("AI provider failure")

        try:
            usage = response.usage
            if usage:
                self.logger.log("OPENAI_USAGE", {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens
                })

                # ✅ Atomic Counter Update (Critical)
                check_and_update(usage.total_tokens)

        except Exception:
            pass

        try:
            answer = response.choices[0].message.content
            if not answer:
                return self.escalate("Empty AI response")
            return answer
        except Exception as e:
            self.logger.log("OPENAI_RESPONSE_PARSE_FAILURE", str(e))
            return self.escalate("AI response failure")

    def escalate(self, reason):
        return f"ESCALATE TO SME: {reason}"

    def detect_difficulty(self, question):
        for k in ["prove", "derive", "theorem"]:
            if k in question.lower():
                return "advanced"
        return "basic"
