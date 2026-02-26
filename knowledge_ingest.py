import os
import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "curionest"

def ingest_document(file_path, subject, chapter, source, version):

    print(f"Ingesting: {file_path}")

    loader = PyPDFLoader(file_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.split_documents(documents)

    # ✅ CRITICAL FIX — PersistentClient (Modern Chroma)
    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False)
    )

    collection = client.get_or_create_collection(COLLECTION_NAME)

    embedder = OpenAIEmbeddings()
    texts = [c.page_content for c in chunks]

    print("Generating embeddings...")
    embeddings = embedder.embed_documents(texts)

    if not embeddings or len(embeddings) != len(texts):
        raise RuntimeError("Embeddings generation failed")

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