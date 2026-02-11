import os
from openai import OpenAI

class StudentSupportAgentV4:
    def __init__(self, rag_store):
        self.rag_store = rag_store
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def receive_question(self, question, context):
        identified = self.identify_context(question, context)
        decision = self.decide_action(identified)
        if decision == "RESPOND":
            return self.respond(question, identified)
        return self.escalate(identified["escalation_reason"])

    def identify_context(self, question, context):
        return {
            "question": question,
            "subject": context.get("subject"),
            "chapter": context.get("chapter"),
            "difficulty": self.detect_difficulty(question)
        }

    def decide_action(self, identified):
        if identified["difficulty"] == "advanced":
            identified["escalation_reason"] = "Advanced question requires teacher"
            return "ESCALATE"
        return "RESPOND"

    def respond(self, question, identified):
        chunks = self.rag_store.search(question, identified["subject"], identified["chapter"])
        if not chunks:
            return self.escalate("No syllabus content found")
        return self.explain_with_ai(question, chunks)

    def explain_with_ai(self, question, chunks):
        content = "\n".join(chunks)
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Answer ONLY from provided content."},
                {"role": "user", "content": f"Content:\n{content}\n\nQuestion:\n{question}"}
            ]
        )
        return response.choices[0].message.content

    def escalate(self, reason):
        return f"ESCALATE TO SME: {reason}"

    def detect_difficulty(self, question):
        for k in ["prove", "derive", "theorem"]:
            if k in question.lower():
                return "advanced"
        return "basic"
