import os
import chromadb
from chromadb.config import Settings

from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

COLLECTION_NAME = "curionest"


def ingest_document(file_path, subject, chapter, source, version):

    print(f"Ingesting: {file_path}")

    # =========================
    # Loader Selection
    # =========================

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        loader = PyPDFLoader(file_path)

    elif ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")

    else:
        raise ValueError(f"Unsupported file type: {ext}")

    documents = loader.load()

    # =========================
    # Chunking
    # =========================

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120
    )

    chunks = splitter.split_documents(documents)

    # =========================
    # Vector DB Setup
    # =========================

    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False)
    )

    collection = client.get_or_create_collection(COLLECTION_NAME)

    # =========================
    # Embeddings
    # =========================

    embedder = OpenAIEmbeddings()

    texts = [c.page_content for c in chunks]

    print("Generating embeddings...")

    embeddings = embedder.embed_documents(texts)

    if not embeddings or len(embeddings) != len(texts):
        raise RuntimeError("Embeddings generation failed")

    # =========================
    # Store Vectors
    # =========================

    print("Storing vectors...")

    for idx, (text, emb) in enumerate(zip(texts, embeddings)):

        collection.add(
            ids=[f"{chapter}_{version}_{idx}"],
            documents=[text],
            embeddings=[emb],
            metadatas=[{
                "subject": subject,
                "chapter": chapter,
                "source": source,
                "version": version
            }]
        )

    print(f"Stored {len(chunks)} chunks successfully")