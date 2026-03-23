import os
import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService
from langchain_openai import OpenAIEmbeddings


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "chroma_db"))

COLLECTION_NAME = "curionest"

# distance threshold for semantic filtering
DISTANCE_THRESHOLD = float(os.getenv("RAG_DISTANCE_THRESHOLD", "0.5"))

# max chunks returned
MAX_CHUNKS = int(os.getenv("RAG_MAX_CHUNKS", "5"))


class ChromaRAGStore:

    def __init__(self):

        os.makedirs(CHROMA_DIR, exist_ok=True)

        self.logger = LoggingService()

        # ---------- Chroma Client ----------

        self.client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False)
        )

        # ---------- Embedding Model ----------

        try:
            self.embedder = OpenAIEmbeddings(
                model="text-embedding-3-small"
            )
        except Exception as e:
            self.logger.log("EMBEDDING_INIT_ERROR", str(e))
            raise e

        # ---------- Collection ----------

        try:
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            self.logger.log("CHROMA_COLLECTION_ERROR", str(e))
            raise e

    # =====================================================
    # SEARCH
    # =====================================================

    def search(self, query, subject, chapter=None, k=None):

        if not query or not subject:
            return []

        k = k or MAX_CHUNKS

        # ---------- EMBEDDING ----------

        try:
            query_embedding = self.embedder.embed_query(query)
        except Exception as e:
            self.logger.log("EMBEDDING_FAILURE", str(e))
            return []

        # ---------- QUERY ----------

        try:

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

        # ---------- NO RESULT ----------

        if not documents or not documents[0]:

            self.logger.log("RAG_EMPTY_RESULT", {
                "query": query[:80],
                "subject": subject,
                "chapter": chapter
            })

            return []

        docs = documents[0]

        # Ensure distances always match docs length
        if distances and distances[0]:
            dists = distances[0]
        else:
            dists = [None] * len(docs)

        # ---------- FILTER ----------

        filtered_docs = []

        for doc, dist in zip(docs, dists):

            # Keep if:
            # - distance missing (fail-safe)
            # - OR within threshold
            if dist is None or dist <= DISTANCE_THRESHOLD:
                filtered_docs.append(doc)

        # ---------- FALLBACK (CRITICAL) ----------

        if not filtered_docs:

            self.logger.log("RAG_FALLBACK_USED", {
                "query": query[:80],
                "reason": "all results filtered out"
            })

            filtered_docs = docs[:MAX_CHUNKS]

        # enforce max limit
        filtered_docs = filtered_docs[:MAX_CHUNKS]

        # ---------- LOG ----------

        self.logger.log("RAG_SUCCESS", {
            "query": query[:80],
            "subject": subject,
            "chapter": chapter,
            "returned_chunks": len(filtered_docs),
            "raw_chunks": len(docs),
            "sample_distances": dists[:3],
            "threshold": DISTANCE_THRESHOLD
        })

        return filtered_docs