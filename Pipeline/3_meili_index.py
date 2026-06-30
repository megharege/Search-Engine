"""
STEP 3: BULK INDEX DOCUMENTS INTO MEILISEARCH
Reads corpus_tagged.jsonl and uploads all chunks in batches.

Usage:
    python 3_meili_index.py --input corpus_tagged.jsonl

Prereqs:
    MeiliSearch running + 2_meili_setup.py already run
"""

import meilisearch
import json
import argparse
import time

MEILI_URL = "http://localhost:7700"
MEILI_KEY = "ayurveda-dev-key"
INDEX_NAME = "ayurveda"
BATCH_SIZE = 500


def wait_for_task(client, task_uid, timeout=120):
    for _ in range(timeout):
        task = client.get_task(task_uid)
        if task.status == "succeeded":
            return task
        if task.status == "failed":
            raise RuntimeError(f"Task failed: {task.error}")
        time.sleep(1)
    raise TimeoutError(f"Task {task_uid} timed out")


def clean_chunk(chunk: dict) -> dict:
    """Ensure chunk_id is safe for MeiliSearch primary key (no dots/slashes)."""
    c = dict(chunk)
    # MeiliSearch primary key cannot contain dots
    c["chunk_id"] = str(c.get("chunk_id", "")).replace(".", "_").replace("/", "_")

    # Ensure tag fields are always lists (not None)
    for field in ["dosha", "roga", "dravya", "karma", "categories_found"]:
        if not isinstance(c.get(field), list):
            c[field] = []

    # Ensure string fields are never None
    for field in ["sanskrit_text", "transliteration", "commentary", "topic_heading",
                  "chapter_title", "sthana", "primary_category", "content_type"]:
        if c.get(field) is None:
            c[field] = ""

    return c


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="corpus_tagged.jsonl")
    parser.add_argument("--source-file", default="", help="Tag all docs with this book name")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        chunks = [clean_chunk(json.loads(line)) for line in f if line.strip()]

    # Optionally tag with source file name
    if args.source_file:
        for c in chunks:
            c["source_file"] = args.source_file

    print(f"Uploading {len(chunks)} chunks to MeiliSearch...")

    client = meilisearch.Client(MEILI_URL, MEILI_KEY)
    index = client.index(INDEX_NAME)

    total = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        task = index.add_documents(batch, primary_key="chunk_id")
        wait_for_task(client, task.task_uid)
        total += len(batch)
        print(f"  Indexed {total}/{len(chunks)}")

    # Verify
    stats = index.get_stats()
    print(f"\nDone. Total documents in index: {stats.number_of_documents}")


if __name__ == "__main__":
    main()
