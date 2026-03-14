import os
import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService
from langchain_openai import OpenAIEmbeddings


# ================= PATH =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "chroma_db"))

COLLECTION_NAME = "curionest"


# ================= RAG STORE =================

class ChromaRAGStore:

    def __init__(self):

        os.makedirs(CHROMA_DIR, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False)
        )

        self.logger = LoggingService()

        # OpenAI embedding model
        self.embedder = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    # ================= SEARCH =================

    def search(self, query, subject, chapter=None, k=5):

        if not query or not subject:
            return []

        try:

            query_embedding = self.embedder.embed_query(query)

            # Metadata filter
            where_filter = {"subject": subject}

            if chapter:
                where_filter["chapter"] = chapter

            res = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where=where_filter,
                include=["documents", "distances"]
            )

        except Exception as e:

            self.logger.log("RAG_QUERY_FAILURE", str(e))
            return []

        documents = res.get("documents")
        distances = res.get("distances")

        if not documents or not documents[0]:

            self.logger.log("RAG_EMPTY_RESULT", {
                "query": query[:80],
                "subject": subject,
                "chapter": chapter
            })

            return []

        docs = documents[0]
        dists = distances[0]

        # ================= FILTER LOW QUALITY =================

        filtered = []

        for doc, dist in zip(docs, dists):

            # Distance threshold tuned for OpenAI embeddings
            if dist < 1.1:
                filtered.append((doc, dist))

        if not filtered:

            self.logger.log("RAG_LOW_SIMILARITY", {
                "query": query[:80],
                "subject": subject,
                "chapter": chapter
            })

            return []

        # ================= SORT BY BEST MATCH =================

        filtered.sort(key=lambda x: x[1])

        final_docs = [doc for doc, _ in filtered]

        self.logger.log("RAG_SUCCESS", {
            "query": query[:80],
            "subject": subject,
            "chapter": chapter,
            "chunks": len(final_docs)
        })

        return final_docs

    # ================= VALIDATION =================

    def validate_chapter(self, subject: str, chapter: str):

        try:

            res = self.collection.get(
                where={
                    "subject": subject,
                    "chapter": chapter
                },
                include=["documents"]
            )

            docs = res.get("documents", [])

            if not docs:

                return {
                    "valid": False,
                    "reason": "No documents found",
                    "count": 0
                }

            return {
                "valid": True,
                "reason": "OK",
                "count": len(docs)
            }

        except Exception as e:

            return {
                "valid": False,
                "reason": str(e),
                "count": 0
            }