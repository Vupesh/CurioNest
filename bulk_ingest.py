import os
from knowledge_ingest import ingest_document
from engine.rag import ChromaRAGStore

DOCS_DIR = "docs"
VERSION = "v1"


def scan_and_ingest():
    total_files = 0

    for subject in os.listdir(DOCS_DIR):
        subject_path = os.path.join(DOCS_DIR, subject)

        if not os.path.isdir(subject_path):
            continue

        for chapter in os.listdir(subject_path):
            chapter_path = os.path.join(subject_path, chapter)

            if not os.path.isdir(chapter_path):
                continue

            for file in os.listdir(chapter_path):
                if not file.lower().endswith(".pdf"):
                    continue

                file_path = os.path.join(chapter_path, file)

                print(f"Ingesting → {subject} | {chapter} | {file}")

                ingest_document(
                    file_path=file_path,
                    subject=subject,
                    chapter=chapter,
                    source="client_bulk_upload",
                    version=VERSION
                )

                total_files += 1

    print(f"\nTotal PDFs processed: {total_files}")


def validate_all_chapters():
    print("\n=== PHASE 1 VALIDATION REPORT ===\n")

    rag = ChromaRAGStore()

    for subject in os.listdir(DOCS_DIR):
        subject_path = os.path.join(DOCS_DIR, subject)

        if not os.path.isdir(subject_path):
            continue

        for chapter in os.listdir(subject_path):
            chapter_path = os.path.join(subject_path, chapter)

            if not os.path.isdir(chapter_path):
                continue

            result = rag.validate_chapter(subject, chapter)

            if result["valid"]:
                print(
                    f"✅ {subject} - {chapter} : OK "
                    f"(chunks={result['count']}, similarity={result.get('similarity')})"
                )
            else:
                print(
                    f"❌ {subject} - {chapter} : FAILED "
                    f"({result['reason']})"
                )


if __name__ == "__main__":
    scan_and_ingest()
    validate_all_chapters()
    