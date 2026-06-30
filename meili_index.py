"""
OPTIMIZED MEILISEARCH INDEXING
Bulk uploads JSONL with batch concurrency and pre-cleaning for speed.

Usage:
    python meili_index.py --input sushruta.jsonl --source-file "Sushruta Samhita"
    python meili_index.py --input bhavaprakasa.jsonl --source-file "Bhavaprakasa Nighantu"
    python meili_index.py --input madhavanidanam.jsonl --source-file "Madhavanidanam"
    python meili_index.py --input sharangadhara.jsonl --source-file "Sharangadhara Samhita"
"""

import meilisearch
import json
import argparse
import time

MEILI_URL = "http://localhost:7700"
MEILI_KEY = "ayurveda-dev-key"
INDEX_NAME = "ayurveda"
BATCH_SIZE = 500


def wait(client, task_uid, timeout=180):
    for _ in range(timeout):
        t = client.get_task(task_uid)
        if t.status == "succeeded":
            return t
        if t.status == "failed":
            raise RuntimeError(t.error)
        time.sleep(1)
    raise TimeoutError(f"Task {task_uid} timed out")


def clean_chunk(chunk: dict, source_file: str) -> dict:
    c = dict(chunk)
    c["chunk_id"] = str(c.get("chunk_id", "")).replace(".", "_").replace("/", "_").replace(" ", "_")
    c["source_file"] = source_file

    for field in ["categories_found"]:
        if not isinstance(c.get(field), list):
            c[field] = []

    for field in ["sanskrit_text", "transliteration", "commentary", "topic_heading",
                  "chapter_title", "sthana", "primary_category", "verse_id", "source_lines"]:
        if c.get(field) is None:
            c[field] = ""

    if c.get("chapter_number") is None:
        c["chapter_number"] = 0

    return c


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--source-file", required=True, help="Book name shown in UI filter")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        chunks = [clean_chunk(json.loads(line), args.source_file) for line in f if line.strip()]

    print(f"Uploading {len(chunks)} chunks from '{args.source_file}'...")

    client = meilisearch.Client(MEILI_URL, MEILI_KEY)
    index = client.index(INDEX_NAME)

    # Fire all batch uploads first, then wait on tasks — much faster than
    # waiting after each batch sequentially
    task_uids = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        task = index.add_documents(batch, primary_key="chunk_id")
        task_uids.append(task.task_uid)

    print(f"  {len(task_uids)} batch(es) submitted, waiting for completion...")
    for uid in task_uids:
        wait(client, uid)

    stats = index.get_stats()
    print(f"Done. Total documents in index: {stats.number_of_documents}")


if __name__ == "__main__":
    main()
