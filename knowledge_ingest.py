import os
import uuid
import chromadb

from chromadb.config import Settings

from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

COLLECTION_NAME = "curionest"


def normalize(value: str):
    """Normalize metadata fields"""
    return value.strip().lower().replace(" ", "_")


def ingest_document(file_path, subject, chapter, source, version):

    print(f"\nIngesting: {file_path}")

    file_name = os.path.basename(file_path)

    subject = normalize(subject)
    chapter = normalize(chapter)

    ext = os.path.splitext(file_path)[1].lower()

    # ----------------------------
    # Loader selection
    # ----------------------------

    if ext == ".pdf":
        loader = PyPDFLoader(file_path)

    elif ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")

    else:
        raise ValueError(f"Unsupported file type: {ext}")

    documents = loader.load()

    if not documents:
        print("No documents loaded")
        return

    # ----------------------------
    # Chunking (optimized)
    # ----------------------------

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=450,
        chunk_overlap=80
    )

    chunks = splitter.split_documents(documents)

    if not chunks:
        print("No chunks created — skipping file")
        return

    # ----------------------------
    # Vector DB connection
    # ----------------------------

    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    # ----------------------------
    # Embedding model
    # ----------------------------

    embedder = OpenAIEmbeddings(
        model="text-embedding-3-small"
    )

    texts = []

    for c in chunks:

        clean_text = c.page_content.strip()

        if len(clean_text) < 50:
            continue

        texts.append(clean_text)

    if not texts:
        print("All chunks filtered — nothing to store")
        return

    embeddings = embedder.embed_documents(texts)

    # ----------------------------
    # Metadata creation
    # ----------------------------

    ids = []
    metadata = []

    for text in texts:

        ids.append(f"{chapter}_{uuid.uuid4().hex}")

        metadata.append({
            "subject": subject,
            "chapter": chapter,
            "source": source,
            "file": file_name,
            "version": version
        })

    # ----------------------------
    # Store vectors
    # ----------------------------

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadata
    )

    print(f"Stored {len(texts)} chunks successfully")