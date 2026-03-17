import os
import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService
from langchain_openai import OpenAIEmbeddings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "chroma_db"))

COLLECTION_NAME = "curionest"

# distance threshold for valid semantic matches
DISTANCE_THRESHOLD = float(os.getenv("RAG_DISTANCE_THRESHOLD", "0.35"))

# max chunks returned to agent
MAX_CHUNKS = int(os.getenv("RAG_MAX_CHUNKS", "5"))

class ChromaRAGStore:
    def __init__(self):
        os.makedirs(CHROMA_DIR, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False)
        )

        self.logger = LoggingService()

        self.embedder = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    def search(self, query, subject, chapter=None, k=5):
        if not query or not subject:
            return []

        try:
            query_embedding = self.embedder.embed_query(query)

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
        dists = distances[0] if distances else []

        # filter weak semantic matches
        filtered_docs = []

        for doc, dist in zip(docs, dists):
            if dist <= DISTANCE_THRESHOLD:
                filtered_docs.append(doc)

        # enforce max chunk limit
        filtered_docs = filtered_docs[:MAX_CHUNKS]

        self.logger.log("RAG_SUCCESS", {
            "query": query[:80],
            "subject": subject,
            "chapter": chapter,
            "chunks": len(filtered_docs),
            "distance_threshold": DISTANCE_THRESHOLD
        })

        return filtered_docs