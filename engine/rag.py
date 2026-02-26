import os
import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService

# ================= CONTROLLED CONSTANTS =================

MAX_DISTANCE_CAP = 0.40
BEST_MATCH_MARGIN = 0.05
COHERENCE_SPREAD_LIMIT = 0.12
CONFIDENCE_DIVISOR = 0.40
MIN_RETRIEVAL_SCORE = 0.60

# ================= PATH RESOLUTION =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "chroma_db"))
COLLECTION_NAME = "curionest"

# ================= HELPERS =================

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

# ================= RAG STORE =================

class ChromaRAGStore:

    def __init__(self):

        # Ensure the DB folder exists
        os.makedirs(CHROMA_DIR, exist_ok=True)

        # Use the modern persistent client
        self.client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False)
        )

        # Logger initialization
        self.logger = LoggingService()

        # Create or validate collection with cosine metric
        self.collection = self._ensure_cosine_collection()

    def _ensure_cosine_collection(self):
        """
        Phase-1 safety gate: force cosine distance (scoring logic depends on it).
        Never deletes live data. Logs every outcome for auditability.
        """

        try:
            collection = self.client.get_collection(name=COLLECTION_NAME)
            metadata = collection.metadata or {}
            current_space = metadata.get("hnsw:space")

            # Already correct
            if current_space == "cosine":
                self.logger.log("RAG_COLLECTION_READY", {
                    "collection": COLLECTION_NAME,
                    "space": "cosine",
                    "action": "existing",
                    "count": collection.count()
                })
                return collection

            # Wrong distance metric: migration required
            count = collection.count()
            self.logger.log("RAG_COLLECTION_MIGRATION_REQUIRED", {
                "collection": COLLECTION_NAME,
                "old_space": current_space,
                "count": count
            })

            # If collection has data — DO NOT DESTROY IT
            if count > 0:
                self.logger.log("RAG_MIGRATION_BLOCKED", {
                    "reason": "non_empty_collection",
                    "count": count,
                    "warning": "Using L2 / incompatible metric. Scoring may be off until DB is cleared manually."
                })
                return collection

            # Safe to delete empty collection
            self.client.delete_collection(name=COLLECTION_NAME)
            self.logger.log("RAG_COLLECTION_MIGRATED", {
                "collection": COLLECTION_NAME,
                "old_space": current_space,
                "new_space": "cosine"
            })

        except ValueError:
            # Collection did not exist; will be created
            pass
        except Exception as e:
            # Log unexpected errors
            self.logger.log("RAG_COLLECTION_ERROR", {"error": str(e)})

        # Create fresh cosine collection
        collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        self.logger.log("RAG_COLLECTION_READY", {
            "collection": COLLECTION_NAME,
            "space": "cosine",
            "action": "created",
            "count": collection.count()
        })
        return collection

    def search(self, query, subject, chapter, k=3):

        if not query or not subject or not chapter:
            self.logger.log("RAG_INVALID_INPUT", {
                "query": bool(query), "subject": bool(subject), "chapter": bool(chapter)
            })
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
            self.logger.log("RAG_QUERY_FAILURE", str(e))
            return []

        documents = res.get("documents")
        distances = res.get("distances")
        if not documents or not distances or not documents[0]:
            self.logger.log("RAG_NO_VECTORS_FOUND", {"subject": subject, "chapter": chapter})
            return []

        docs = documents[0]
        dists = distances[0]

        # Apply Block 9.12 filtering logic
        best_distance = min(dists)
        dynamic_threshold = min(best_distance + BEST_MATCH_MARGIN, MAX_DISTANCE_CAP)

        filtered_chunks = []
        filtered_distances = []
        rejection_reasons = []

        for doc, dist in zip(docs, dists):
            if dist > dynamic_threshold:
                rejection_reasons.append({"reason": "distance_rejected", "distance": dist})
                continue
            if not lexical_overlap(query, doc):
                rejection_reasons.append({"reason": "lexical_rejected", "distance": dist})
                continue
            filtered_chunks.append(doc)
            filtered_distances.append(dist)

        score = retrieval_score(filtered_distances)
        coherent = chunks_are_coherent(filtered_distances)

        # Block 9.13 diagnostics log
        self.logger.log("RAG_DECISION_TRACE", {
            "raw_distances": dists,
            "best_distance": best_distance,
            "dynamic_threshold": dynamic_threshold,
            "accepted_chunks": len(filtered_chunks),
            "retrieval_score": score,
            "coherent": coherent,
            "rejections": rejection_reasons[:5]
        })

        # Failure classification
        if not filtered_chunks:
            self.logger.log("RAG_RETRIEVAL_FAILURE", "all_chunks_rejected")
            return []
        if score < MIN_RETRIEVAL_SCORE:
            self.logger.log("RAG_LOW_CONFIDENCE", score)
            return []
        if not coherent:
            self.logger.log("RAG_INCOHERENT_CONTEXT", filtered_distances)
            return []

        return filtered_chunks

    def validate_chapter(self, subject: str, chapter: str) -> dict:
        """
        Phase-1 sanity check: ensures chapter has vectors and basic semantic quality.
        """
        try:
            count = self.collection.count(where={"subject": subject, "chapter": chapter})
            if count == 0:
                return {"valid": False, "count": 0, "reason": "No documents"}

            # sanity retrieval test
            test_query = f"summary of {chapter} in {subject}"
            res = self.collection.query(
                query_texts=[test_query],
                n_results=1,
                where={"subject": subject, "chapter": chapter},
                include=["distances"]
            )
            best_similarity = None
            if res and res.get("distances") and res["distances"][0]:
                best_similarity = 1.0 - res["distances"][0][0]
                if best_similarity < 0.65:
                    return {
                        "valid": False,
                        "count": count,
                        "reason": f"Low semantic density (sim={best_similarity:.2f})"
                    }

            return {"valid": True, "count": count, "reason": "OK", "test_similarity": best_similarity}
        except Exception as e:
            return {"valid": False, "count": 0, "reason": str(e)}