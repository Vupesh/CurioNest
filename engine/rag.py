import os
from openai import OpenAI
import chromadb

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class ChromaRAGStore:

    def __init__(self):

        self.client = OpenAI()

        self.chroma = chromadb.Client()

        self.collection = self.chroma.get_or_create_collection(
            name="curionest_knowledge"
        )

    # ================= NORMALIZE =================
    def _normalize(self, text):
        return text.strip().lower() if text else ""

    # ================= RETRIEVE =================
    def retrieve(self, query, context, k=3):

        chapter = self._normalize(context.get("chapter", ""))

        # 🔥 STEP 1: TRY STRICT MATCH
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=k,
                where={"chapter": chapter}
            )

            docs = results.get("documents", [[]])[0]

            if docs:
                return docs

        except:
            pass

        # 🔥 STEP 2: FALLBACK (NO FILTER)
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=k
            )

            docs = results.get("documents", [[]])[0]

            return docs

        except:
            return []

    # ================= GENERATE =================
    def generate(self, query, docs):

        context_text = "\n".join(docs)

        prompt = f"""
You are a friendly school tutor.

RULES:
- Answer using given context
- Keep it SHORT (2–3 lines)
- Use SIMPLE language
- Add ONE small example
- DO NOT use "Definition / Key Idea"
- If unsure, still try to explain basic idea

CONTEXT:
{context_text}

QUESTION:
{query}
"""

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return response.choices[0].message.content.strip()

        except:
            return None

    # ================= MAIN =================
    def query(self, question, context):

        docs = self.retrieve(question, context)

        # 🔥 SAFETY: if still no docs, allow basic fallback
        if not docs:
            return None

        answer = self.generate(question, docs)

        return answer