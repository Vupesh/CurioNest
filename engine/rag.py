import os
import re
import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService


# ================= STATIC SAFETY CONSTANTS =================
# These act as fallback defaults before calibration stabilizes

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
    def normalize(text):
        return re.findall(r"\b\w+\b", text.lower())

    query_terms = set(normalize(query))
    chunk_terms = set(normalize(chunk))

    return len(query_terms.intersection(chunk_terms)) >= min_hits


# ================= RAG STORE =================

class ChromaRAGStore:

    def __init__(self):

        os.makedirs(CHROMA_DIR, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False)
        )

        self.logger = LoggingService()

        # 9.14 Calibration state (in-memory, safe)
        self.calibration_stats = {}

        self.collection = self._ensure_cosine_collection()

    # ================= COSINE SAFETY =================

    def _ensure_cosine_collection(self):

        try:
            collection = self.client.get_collection(name=COLLECTION_NAME)
            metadata = collection.metadata or {}
            current_space = metadata.get("hnsw:space")

            if current_space == "cosine":
                return collection

            count = collection.count()

            self.logger.log("RAG_COLLECTION_MIGRATION_REQUIRED", {
                "old_space": current_space,
                "count": count
            })

            if count > 0:
                self.logger.log("RAG_MIGRATION_BLOCKED", {
                    "reason": "non_empty_collection"
                })
                return collection

            self.client.delete_collection(name=COLLECTION_NAME)

        except ValueError:
            pass
        except Exception as e:
            self.logger.log("RAG_COLLECTION_ERROR", {"error": str(e)})

        return self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    # ================= 9.14 CALIBRATION =================

    def _update_calibration(self, subject, chapter, best_distance):
        key = (subject, chapter)

        stats = self.calibration_stats.get(key, {
            "count": 0,
            "mean": 0.0,
            "m2": 0.0
        })

        stats["count"] += 1
        delta = best_distance - stats["mean"]
        stats["mean"] += delta / stats["count"]
        delta2 = best_distance - stats["mean"]
        stats["m2"] += delta * delta2

        self.calibration_stats[key] = stats

    def _adaptive_distance_cap(self, subject, chapter):
        key = (subject, chapter)
        stats = self.calibration_stats.get(key)

        if not stats or stats["count"] < 5:
            return MAX_DISTANCE_CAP

        variance = stats["m2"] / max(stats["count"] - 1, 1)
        std_dev = variance ** 0.5

        adaptive = stats["mean"] + (1.5 * std_dev)

        return min(adaptive, 0.85)

    # ================= SEARCH =================

    def search(self, query, subject, chapter, k=3):

        if not query or not subject or not chapter:
            return []

        try:
            res = self.collection.query(
                query_texts=[query],
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

        # 9.14 calibration update
        self._update_calibration(subject, chapter, best_distance)

        adaptive_cap = self._adaptive_distance_cap(subject, chapter)

        dynamic_threshold = min(best_distance + BEST_MATCH_MARGIN, adaptive_cap)

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