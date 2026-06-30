"""
STEP 2: MEILISEARCH INDEX SETUP
Configures the MeiliSearch index with correct field settings and the embedding model.
Run ONCE after starting the MeiliSearch server.

Usage:
    python 2_meili_setup.py

Prereqs:
    pip install meilisearch
    # Start MeiliSearch first:
    curl -L https://install.meilisearch.com | sh
    ./meilisearch --master-key='ayurveda-dev-key' --no-analytics
"""

import meilisearch
import time

MEILI_URL = "http://localhost:7700"
MEILI_KEY = "ayurveda-dev-key"
INDEX_NAME = "ayurveda"


def wait_for_task(client, task_uid, timeout=30):
    """Poll until a MeiliSearch task completes."""
    for _ in range(timeout):
        task = client.get_task(task_uid)
        if task.status in ("succeeded", "failed"):
            return task
        time.sleep(1)
    raise TimeoutError(f"Task {task_uid} timed out")


def setup():
    client = meilisearch.Client(MEILI_URL, MEILI_KEY)

    # Check server is up
    try:
        client.health()
        print("MeiliSearch is running.")
    except Exception:
        print("ERROR: MeiliSearch not reachable at", MEILI_URL)
        print("Start it with: ./meilisearch --master-key='ayurveda-dev-key'")
        return

    # Create or get index
    try:
        index = client.get_index(INDEX_NAME)
        print(f"Index '{INDEX_NAME}' already exists.")
    except Exception:
        task = client.create_index(INDEX_NAME, {"primaryKey": "chunk_id"})
        wait_for_task(client, task.task_uid)
        index = client.get_index(INDEX_NAME)
        print(f"Created index '{INDEX_NAME}'.")

    # 1. Searchable attributes — order = BM25 weight priority
    t = index.update_searchable_attributes([
        "topic_heading",
        "transliteration",
        "commentary",
        "chapter_title",
        "sanskrit_text",
        "sthana",
        "roga",
        "dravya"
    ])
    wait_for_task(client, t.task_uid)
    print("Searchable attributes set.")

    # 2. Filterable attributes — enables filter= in search queries
    t = index.update_filterable_attributes([
        "sthana",
        "chapter_number",
        "primary_category",
        "dosha",
        "roga",
        "dravya",
        "karma",
        "content_type",
        "source_file"
    ])
    wait_for_task(client, t.task_uid)
    print("Filterable attributes set.")

    # 3. Sortable attributes
    t = index.update_sortable_attributes(["chapter_number"])
    wait_for_task(client, t.task_uid)
    print("Sortable attributes set.")

    # 4. Embedder for semantic/hybrid search (MeiliSearch >= 1.6)
    # Uses HuggingFace multilingual-e5-small — runs locally, no API key needed
    # documentTemplate defines what text gets embedded per document
    t = index.update_embedders({
        "default": {
            "source": "huggingFace",
            "model": "intfloat/multilingual-e5-small",
            "documentTemplate": "{{doc.topic_heading}} {{doc.transliteration}} {{doc.commentary}}"
        }
    })
    wait_for_task(client, t.task_uid)
    print("Embedder configured (multilingual-e5-small).")

    # 5. Ranking rules — default order is fine, keeping explicit for clarity
    t = index.update_ranking_rules([
        "words",
        "typo",
        "proximity",
        "attribute",
        "sort",
        "exactness"
    ])
    wait_for_task(client, t.task_uid)
    print("Ranking rules set.")

    print("\nSetup complete. Ready to index documents.")


if __name__ == "__main__":
    setup()
