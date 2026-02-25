from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

CHROMA_DIR = "chroma_db"

def ingest_document(file_path, subject, chapter, source, version):
    print(f"Ingesting: {file_path}")

    subject_n = subject.strip()
    chapter_n = chapter.strip()
    source_n = source.strip().lower()
    version_n = version.strip().lower()

    embeddings = OpenAIEmbeddings()

    db = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings
    )

    existing = db.get(
        where={
            "$and": [
                {"subject": subject_n},
                {"chapter": chapter_n},
                {"source": source_n},
                {"version": version_n}
            ]
        }
    )

    if existing["ids"]:
        print("ABORTED — This document version already exists.")
        return

    loader = PyPDFLoader(file_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120
    )

    chunks = splitter.split_documents(documents)

    for c in chunks:
        c.metadata = {
            "subject": subject_n,
            "chapter": chapter_n,
            "source": source_n,
            "version": version_n
        }

    Chroma.from_documents(
        chunks,
        embeddings,
        persist_directory=CHROMA_DIR
    )

    print(f"Stored {len(chunks)} chunks")