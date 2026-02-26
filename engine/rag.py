import os
import re
import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService
from langchain_openai import OpenAIEmbeddings


# ================= CONSTANTS =================

MAX_DISTANCE_CAP = 0.85
BEST_MATCH_MARGIN = 0.05
COHERENCE_SPREAD_LIMIT = 0.20
CONFIDENCE_DIVISOR = 1.0
MIN_RETRIEVAL_SCORE = 0.20


# ================= PATH =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "chroma_db"))
COLLECTION_NAME = "curionest"


# ================= HELPERS =================

def normalize_text(text):
    return re.findall(r"\b\w+\b", text.lower())


def lexical_overlap(query, chunk, min_hits=2):
    query_terms = set(normalize_text(query))
    chunk_terms = set(normalize_text(chunk))
    return len(query_terms.intersection(chunk_terms)) >= min_hits


def chunks_are_coherent(distances, spread_limit=COHERENCE_SPREAD_LIMIT):
    if len(distances) < 2:
        return True
    return (max(distances) - min(distances)) < spread_limit


def retrieval_score(distances, divisor=CONFIDENCE_DIVISOR):
    if not distances:
        return 0.0
    avg = sum(distances) / len(distances)
    return max(0.0, 1 - (avg / divisor))


# ================= RAG STORE =================

class ChromaRAGStore:

    def __init__(self):

        os.makedirs(CHROMA_DIR, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False)
        )

        self.logger = LoggingService()
        self.embedder = OpenAIEmbeddings()

        self.collection = self._ensure_cosine_collection()

    # ---------------- COSINE SAFETY ----------------

    def _ensure_cosine_collection(self):
        try:
            collection = self.client.get_collection(name=COLLECTION_NAME)
            metadata = collection.metadata or {}
            if metadata.get("hnsw:space") == "cosine":
                return collection

            count = collection.count()

            if count > 0:
                self.logger.log("RAG_WARNING_NON_COSINE_COLLECTION", {
                    "count": count
                })
                return collection

            self.client.delete_collection(name=COLLECTION_NAME)

        except ValueError:
            pass

        return self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    # ---------------- SEARCH ----------------

    def search(self, query, subject, chapter, k=3):

        if not query or not subject or not chapter:
            return []

        try:
            query_embedding = self.embedder.embed_query(query)

            res = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where={
                    "$and": [
                        {"subject": subject},
                        {"chapter": chapter}
                    ]
                },
                include=["documents", "distances"]
            )

        except Exception as e:
            self.logger.log("RAG_QUERY_FAILURE", str(e))
            return []

        documents = res.get("documents")
        distances = res.get("distances")

        if not documents or not distances or not documents[0]:
            return []

        docs = documents[0]
        dists = distances[0]

        best_distance = min(dists)
        dynamic_threshold = min(best_distance + BEST_MATCH_MARGIN, MAX_DISTANCE_CAP)

        filtered_chunks = []
        filtered_distances = []

        for doc, dist in zip(docs, dists):

            if dist > dynamic_threshold:
                continue

            if not lexical_overlap(query, doc):
                continue

            filtered_chunks.append(doc)
            filtered_distances.append(dist)

        if not filtered_chunks:
            return []

        score = retrieval_score(filtered_distances)
        coherent = chunks_are_coherent(filtered_distances)

        if score < MIN_RETRIEVAL_SCORE:
            return []

        if not coherent:
            return []

        return filtered_chunks
    
    