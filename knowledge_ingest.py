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


def ingest_document(file_path, subject, chapter, source, version):

    print(f"\nIngesting: {file_path}")

    file_name = os.path.basename(file_path)

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        loader = PyPDFLoader(file_path)

    elif ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")

    else:
        raise ValueError(f"Unsupported file type: {ext}")

    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=120
    )

    chunks = splitter.split_documents(documents)

    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    embedder = OpenAIEmbeddings(
        model="text-embedding-3-small"
    )

    texts = []

    for c in chunks:

        text = f"""
Subject: {subject}
Chapter: {chapter}
Source: {file_name}

{c.page_content}
"""

        texts.append(text)

    embeddings = embedder.embed_documents(texts)

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

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadata
    )

    print(f"Stored {len(texts)} chunks successfully")