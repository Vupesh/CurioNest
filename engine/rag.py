import os
import chromadb
from chromadb.config import Settings
from services.logging_service import LoggingService
from langchain_openai import OpenAIEmbeddings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "chroma_db"))

COLLECTION_NAME = "curionest"


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

        if not documents or not documents[0]:

            self.logger.log("RAG_EMPTY_RESULT", {
                "query": query[:80],
                "subject": subject
            })

            return []

        docs = documents[0]

        self.logger.log("RAG_SUCCESS", {
            "query": query[:80],
            "subject": subject,
            "chapter": chapter,
            "chunks": len(docs)
        })

        return docs