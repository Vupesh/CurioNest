import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService


MAX_DISTANCE_CAP = 0.40          # absolute safety ceiling
BEST_MATCH_MARGIN = 0.05         # adaptive margin
COHERENCE_SPREAD_LIMIT = 0.12    # chunk consistency guard
CONFIDENCE_DIVISOR = 0.40        # scoring normalization


def chunks_are_coherent(distances, spread_limit=COHERENCE_SPREAD_LIMIT):
    if len(distances) < 2:
        return True
    return (max(distances) - min(distances)) < spread_limit


def retrieval_score(distances, divisor=CONFIDENCE_DIVISOR):
    if not distances:
        return 0.0
    avg = sum(distances) / len(distances)
    return max(0.0, 1 - (avg / divisor))


def lexical_overlap(query, chunk, min_hits=2):
    query_terms = set(query.lower().split())
    chunk_terms = set(chunk.lower().split())
    return len(query_terms.intersection(chunk_terms)) >= min_hits


class ChromaRAGStore:
    def __init__(self, documents):

        try:
            self.client = chromadb.Client(Settings(
                persist_directory=".chroma",
                anonymized_telemetry=False
            ))
        except Exception:
            raise RuntimeError("ChromaDB initialization failure")

        self.collection = self.client.get_or_create_collection("curionest")
        self.logger = LoggingService()

        try:
            self._ingest(documents)
        except Exception:
            pass  # Never block system startup

    def _ingest(self, documents):

        try:
            existing_data = self.collection.get(include=[])
            existing = set(existing_data.get("ids", []))
        except Exception:
            existing = set()

        for doc in documents:

            if doc.get("id") in existing:
                continue

            try:
                self.collection.add(
                    ids=[doc["id"]],
                    documents=[doc["text"]],
                    metadatas=[{
                        "subject": doc.get("subject"),
                        "chapter": doc.get("chapter")
                    }]
                )
            except Exception:
                continue

    def search(self, query, subject, chapter, k=3):

        if not query or not subject or not chapter:
            return []

        self.logger.log("RAG_SEARCH", {
            "subject": subject,
            "chapter": chapter
        })

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
        filtered_distances = []

        for doc, dist in zip(docs, dists):

            if dist > dynamic_threshold:
                continue

            if not lexical_overlap(query, doc):
                continue

            filtered_chunks.append(doc)
            filtered_distances.append(dist)

        score = retrieval_score(filtered_distances)
        coherent = chunks_are_coherent(filtered_distances)

        self.logger.log("RAG_DIAGNOSTICS", {
            "best_distance": best_distance,
            "dynamic_threshold": dynamic_threshold,
            "filtered_count": len(filtered_chunks),
            "retrieval_score": score,
            "coherent": coherent
        })

        if not filtered_chunks:
            return []

        return filtered_chunks