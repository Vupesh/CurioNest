import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService


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
                continue  # Skip bad documents safely

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

        if not documents or not isinstance(documents, list):
            return []

        first_result = documents[0]

        if not first_result or not isinstance(first_result, list):
            return []

        self.logger.log("RAG_RESULTS", len(first_result))

        return first_result
