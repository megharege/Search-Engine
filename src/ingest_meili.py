"""
Step 3: Ingest combined.jsonl + embeddings.npz into Meilisearch

Two userProvided embedders are registered:
  commentary_embedder      (1024-dim)  ← primary search target
  transliteration_embedder (1024-dim)  ← for shloka-text queries

Filterable attributes:
  book_id, sthana, chapter_number, primary_category, categories_found, verse_id, chunk_id

Requires Meilisearch server running on MEILI_URL (default http://127.0.0.1:7700).

Usage:
    python -m src.ingest_meili
"""
from __future__ import annotations
import json, os
import meilisearch
from src.embed import load_embeddings

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMBINED = os.path.join(ROOT, "data", "combined.jsonl")
INDEX    = "ayur_chunks"
MEILI_URL = os.environ.get("MEILI_URL",       "http://127.0.0.1:7700")
MEILI_KEY = os.environ.get("MEILI_MASTER_KEY", "")

FILTERABLE = [
    "book_id", "book_name", "sthana", "chapter_number",
    "primary_category", "categories_found", "verse_id", "chunk_id",
]
SEARCHABLE = [
    "topic_heading", "commentary", "transliteration",
    "sanskrit_text", "chapter_title", "primary_category", "book_name",
]


def get_client():
    return meilisearch.Client(MEILI_URL, MEILI_KEY or None)


def setup_index(client) -> meilisearch.Index:
    # create index if missing
    try:
        index = client.get_index(INDEX)
    except Exception:
        task = client.create_index(INDEX, {"primaryKey": "global_id"})
        client.wait_for_task(task.task_uid)
        index = client.get_index(INDEX)

    index.update_filterable_attributes(FILTERABLE)
    index.update_searchable_attributes(SEARCHABLE)
    index.update_sortable_attributes(["chapter_number"])

    task = index.update_embedders({
        "commentary_embedder":      {"source": "userProvided", "dimensions": 1024},
        "transliteration_embedder": {"source": "userProvided", "dimensions": 1024},
    })
    client.wait_for_task(task.task_uid)
    print("  Index configured.")
    return index


def ingest(batch_size: int = 200):
    client = get_client()
    index  = setup_index(client)
    embs   = load_embeddings()

    docs = []
    with open(COMBINED, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            e = embs[rec["global_id"]]          # look up embedding by ORIGINAL id
            rec["_vectors"] = {
                "commentary_embedder":      e["commentary"].tolist(),
                "transliteration_embedder": e["transliteration"].tolist(),
            }
            rec["global_id"] = rec["global_id"].replace("::", "-")  # sanitize for Meili primary key
            docs.append(rec)

    total = len(docs)
    print(f"  Uploading {total} docs in batches of {batch_size} ...")
    for i in range(0, total, batch_size):
        batch = docs[i : i + batch_size]
        task  = index.add_documents(batch, primary_key="global_id")
        client.wait_for_task(task.task_uid)
        print(f"    {min(i + batch_size, total)}/{total}")
    print(f"  Done — {total} docs indexed in '{INDEX}'")


if __name__ == "__main__":
    print("== Ingesting into Meilisearch ==")
    ingest()
