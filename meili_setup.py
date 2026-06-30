"""
OPTIMIZED MEILISEARCH SETUP
Performance tuning: typo tolerance disabled on Sanskrit fields, pagination limits,
proximity precision, and search cutoff for fast response times.

Usage:
    python meili_setup.py
"""

import meilisearch
import time

MEILI_URL = "http://localhost:7700"
MEILI_KEY = "ayurveda-dev-key"
INDEX_NAME = "ayurveda"


def wait(client, task_uid, timeout=60):
    for _ in range(timeout):
        t = client.get_task(task_uid)
        if t.status in ("succeeded", "failed"):
            if t.status == "failed":
                raise RuntimeError(t.error)
            return t
        time.sleep(1)
    raise TimeoutError(f"Task {task_uid} timed out")


def setup():
    client = meilisearch.Client(MEILI_URL, MEILI_KEY)
    client.health()
    print("MeiliSearch is up.")

    try:
        index = client.get_index(INDEX_NAME)
        print("Index exists.")
    except Exception:
        t = client.create_index(INDEX_NAME, {"primaryKey": "chunk_id"})
        wait(client, t.task_uid)
        index = client.get_index(INDEX_NAME)
        print("Index created.")

    # Searchable — order = relevance weight
    wait(client, index.update_searchable_attributes([
        "topic_heading", "transliteration", "commentary",
        "chapter_title", "sanskrit_text", "sthana"
    ]).task_uid)

    # Filterable — drives the UI filter sidebar
    wait(client, index.update_filterable_attributes([
        "source_file", "sthana", "chapter_number",
        "primary_category", "categories_found"
    ]).task_uid)

    wait(client, index.update_sortable_attributes(["chapter_number"]).task_uid)

    # Embedder for hybrid/semantic search
    wait(client, index.update_embedders({
        "default": {
            "source": "huggingFace",
            "model": "intfloat/multilingual-e5-small",
            "documentTemplate": "{{doc.topic_heading}} {{doc.transliteration}} {{doc.commentary}}"
        }
    }).task_uid)

    # ── PERFORMANCE TUNING ──────────────────────────────

    # 1. Disable typo tolerance on diacritic-sensitive fields
    #    (ā vs a, ṣ vs s matter in IAST transliteration — typo correction would
    #    return wrong verses)
    wait(client, index.update_typo_tolerance({
        "enabled": True,
        "disableOnAttributes": ["transliteration", "sanskrit_text", "chunk_id", "verse_id"],
        "minWordSizeForTypos": {"oneTypo": 5, "twoTypos": 9}
    }).task_uid)

    # 2. Pagination — cap max results so deep pagination doesn't blow up memory
    wait(client, index.update_pagination_settings({
        "maxTotalHits": 1000
    }).task_uid)

    # 3. Faceting — limit facet values returned (book/sthana/category counts in UI)
    wait(client, index.update_faceting_settings({
        "maxValuesPerFacet": 100
    }).task_uid)

    # 4. Proximity precision — "byWord" is faster than "byAttribute" for our use case
    wait(client, index.update_proximity_precision("byWord").task_uid)

    # 5. Ranking rules — exactness late, since Sanskrit transliteration variants
    #    (ā vs aa) shouldn't penalize relevance too harshly
    wait(client, index.update_ranking_rules([
        "words", "typo", "proximity", "attribute", "sort", "exactness"
    ]).task_uid)

    print("\nOptimized index setup complete.")
    print("- Typo tolerance disabled on Sanskrit/transliteration fields")
    print("- Max 1000 total hits (prevents slow deep pagination)")
    print("- Faceting capped at 100 values/facet")
    print("- byWord proximity precision (faster)")


if __name__ == "__main__":
    setup()
