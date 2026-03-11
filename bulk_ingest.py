import os
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from knowledge_ingest import ingest_document
from engine.rag import ChromaRAGStore

DOCS_DIR = "docs II"
VERSION = "v1"

HASH_FILE = "ingest_hashes.json"


# =====================================================
# HASH UTILITIES (PREVENT DUPLICATE INGESTION)
# =====================================================

def file_hash(path):

    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def load_hashes():

    if os.path.exists(HASH_FILE):

        with open(HASH_FILE, "r") as f:
            return json.load(f)

    return {}


def save_hashes(hashes):

    with open(HASH_FILE, "w") as f:
        json.dump(hashes, f, indent=2)


# =====================================================
# INGEST SINGLE FILE
# =====================================================

def ingest_file(file_path, subject, chapter):

    ingest_document(
        file_path=file_path,
        subject=subject,
        chapter=chapter,
        source="client_bulk_upload",
        version=VERSION
    )


# =====================================================
# BULK INGESTION
# =====================================================

def scan_and_ingest():

    total_files = 0

    hashes = load_hashes()
    new_hashes = {}

    tasks = []

    with ThreadPoolExecutor(max_workers=4) as executor:

        for board in os.listdir(DOCS_DIR):

            board_path = os.path.join(DOCS_DIR, board)

            if not os.path.isdir(board_path):
                continue

            for subject in os.listdir(board_path):

                subject_path = os.path.join(board_path, subject)

                if not os.path.isdir(subject_path):
                    continue

                for chapter in os.listdir(subject_path):

                    chapter_path = os.path.join(subject_path, chapter)

                    if not os.path.isdir(chapter_path):
                        continue

                    for file in os.listdir(chapter_path):

                        if not file.lower().endswith((".pdf", ".txt")):
                            continue

                        file_path = os.path.join(chapter_path, file)

                        h = file_hash(file_path)

                        if file_path in hashes and hashes[file_path] == h:

                            print(f"Skipping unchanged file → {file}")
                            continue

                        print(f"Ingesting → {board} | {subject} | {chapter} | {file}")

                        new_hashes[file_path] = h

                        tasks.append(
                            executor.submit(
                                ingest_file,
                                file_path,
                                subject,
                                chapter
                            )
                        )

                        total_files += 1

        for task in tasks:
            task.result()

    save_hashes(new_hashes)

    print(f"\nTotal files processed: {total_files}")


# =====================================================
# VALIDATION
# =====================================================

def validate_all_chapters():

    print("\n=== PHASE 1 VALIDATION REPORT ===\n")

    rag = ChromaRAGStore()

    for board in os.listdir(DOCS_DIR):

        board_path = os.path.join(DOCS_DIR, board)

        if not os.path.isdir(board_path):
            continue

        for subject in os.listdir(board_path):

            subject_path = os.path.join(board_path, subject)

            if not os.path.isdir(subject_path):
                continue

            for chapter in os.listdir(subject_path):

                chapter_path = os.path.join(subject_path, chapter)

                if not os.path.isdir(chapter_path):
                    continue

                result = rag.validate_chapter(subject, chapter)

                if result["valid"]:

                    print(
                        f"✅ {board} | {subject} | {chapter} : OK "
                        f"(chunks={result['count']}, similarity={result.get('similarity')})"
                    )

                else:

                    print(
                        f"❌ {board} | {subject} | {chapter} : FAILED "
                        f"({result['reason']})"
                    )


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    scan_and_ingest()

    validate_all_chapters()