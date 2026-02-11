import chromadb
from chromadb.config import Settings

class ChromaRAGStore:
    def __init__(self, documents):
        self.client = chromadb.Client(Settings(
            persist_directory=".chroma",
            anonymized_telemetry=False
        ))
        self.collection = self.client.get_or_create_collection("curionest")
        self._ingest(documents)

    def _ingest(self, documents):
        existing = set(self.collection.get(include=[])["ids"])
        for doc in documents:
            if doc["id"] not in existing:
                self.collection.add(
                    ids=[doc["id"]],
                    documents=[doc["text"]],
                    metadatas=[{"subject": doc["subject"], "chapter": doc["chapter"]}]
                )

    def search(self, query, subject, chapter, k=3):
        res = self.collection.query(
            query_texts=[query],
            n_results=k,
            where={"$and": [{"subject": subject}, {"chapter": chapter}]}
        )
        return res.get("documents", [[]])[0]
