import os
import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "..", "chroma_db")
CHROMA_DIR = os.path.abspath(CHROMA_DIR)


MAX_DISTANCE_CAP = 0.40
BEST_MATCH_MARGIN = 0.05


def lexical_overlap(query, chunk, min_hits=2):
    query_terms = set(query.lower().split())
    chunk_terms = set(chunk.lower().split())
    return len(query_terms.intersection(chunk_terms)) >= min_hits


class ChromaRAGStore:

    def __init__(self, documents=None):

        try:
            self.client = chromadb.Client(Settings(
                persist_directory=CHROMA_DIR,
                anonymized_telemetry=False
            ))
        except Exception:
            raise RuntimeError("ChromaDB initialization failure")

        self.collection = self.client.get_or_create_collection("curionest")
        self.logger = LoggingService()

    def search(self, query, subject, chapter, k=3):

        if not query or not subject or not chapter:
            return []

        try:
            res = self.collection.query(
                query_texts=[query],
                n_results=k,
                include=["documents", "distances"],
                where={
                    "$and": [
                        {"subject": subject},
                        {"chapter": chapter}
                    ]
                }
            )
        except Exception as e:
            self.logger.log("RAG_FAILURE", str(e))
            return []

        documents = res.get("documents")
        distances = res.get("distances")

        if not documents or not distances:
            return []

        docs = documents[0]
        dists = distances[0]

        if not docs:
            return []

        best_distance = min(dists)
        dynamic_threshold = min(best_distance + BEST_MATCH_MARGIN, MAX_DISTANCE_CAP)

        filtered_chunks = []

        for doc, dist in zip(docs, dists):

            if dist > dynamic_threshold:
                continue

            if not lexical_overlap(query, doc):
                continue

            filtered_chunks.append(doc)

        return filtered_chunks