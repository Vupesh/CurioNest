from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

CHROMA_DIR = "chroma_db"

def ingest_document(file_path, subject, chapter, source, version):
    print(f"Ingesting: {file_path}")

    loader = PyPDFLoader(file_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120
    )

    chunks = splitter.split_documents(documents)

    for c in chunks:
        c.metadata = {
            "subject": subject,
            "chapter": chapter,
            "source":  source,
            "version": version
        }

    Chroma.from_documents(
        chunks,
        OpenAIEmbeddings(),
        persist_directory=CHROMA_DIR
    )

    print(f"Stored {len(chunks)} chunks")