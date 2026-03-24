import os
from openai import OpenAI
import chromadb

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class ChromaRAGStore:

    def __init__(self):

        self.client = OpenAI()

        # Chroma DB init
        self.chroma = chromadb.Client()

        # Collection (must match your ingest)
        self.collection = self.chroma.get_or_create_collection(
            name="curionest_knowledge"
        )

    # ================= RETRIEVE =================
    def retrieve(self, query, context, k=3):

        subject = context.get("subject", "")
        chapter = context.get("chapter", "")

        results = self.collection.query(
            query_texts=[query],
            n_results=k,
            where={
                "subject": subject,
                "chapter": chapter
            }
        )

        documents = results.get("documents", [[]])[0]

        return documents

    # ================= GENERATE =================
    def generate(self, query, docs):

        context_text = "\n".join(docs)

        prompt = f"""
You are a helpful school tutor.

STRICT RULES:
- Answer ONLY from given context
- If context is insufficient → say "This topic needs teacher guidance"
- Keep answer SHORT (2–3 lines)
- Use SIMPLE language
- Add ONE small example
- DO NOT use "Definition / Key Idea"

CONTEXT:
{context_text}

QUESTION:
{query}
"""

        response = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content.strip()

    # ================= MAIN =================
    def query(self, question, context):

        docs = self.retrieve(question, context)

        # NO CONTEXT → FORCE ESCALATION SIGNAL
        if not docs:
            return "This topic needs teacher guidance."

        answer = self.generate(question, docs)

        return answer