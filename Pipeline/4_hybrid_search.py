"""
STEP 4: HYBRID SEARCH MODULE
Keyword, semantic, and hybrid search over MeiliSearch.
Also supports key-value / filter-only search.

Usage (as module):
    from 4_hybrid_search import search, kv_search

Usage (standalone test):
    python 4_hybrid_search.py "vata dosha jwara treatment"

Prereqs:
    MeiliSearch running with documents indexed
"""

import meilisearch
import json
import argparse

MEILI_URL = "http://localhost:7700"
MEILI_KEY = "ayurveda-dev-key"
INDEX_NAME = "ayurveda"

_client = None
_index = None


def get_index():
    global _client, _index
    if _index is None:
        _client = meilisearch.Client(MEILI_URL, MEILI_KEY)
        _index = _client.index(INDEX_NAME)
    return _index


def search(
    query: str,
    *,
    book: str = None,          # filter by source_file
    sthana: str = None,        # filter by sthana (e.g. "Sutrasthana")
    dosha: str = None,         # filter by dosha tag
    roga: str = None,          # filter by disease tag
    dravya: str = None,        # filter by herb tag
    content_type: str = None,  # filter by content_type
    alpha: float = 0.5,        # 0=keyword only, 1=semantic only, 0.5=hybrid
    top_k: int = 20,
) -> list[dict]:
    """
    Main search function.
    alpha controls the keyword/semantic balance:
        0.0 = pure BM25 keyword search
        0.5 = balanced hybrid (default)
        1.0 = pure vector/semantic search
    """
    index = get_index()

    # Build filter string
    filters = []
    if book:
        filters.append(f'source_file = "{book}"')
    if sthana:
        filters.append(f'sthana = "{sthana}"')
    if dosha:
        filters.append(f'dosha = "{dosha}"')
    if roga:
        filters.append(f'roga = "{roga}"')
    if dravya:
        filters.append(f'dravya = "{dravya}"')
    if content_type:
        filters.append(f'content_type = "{content_type}"')

    params = {
        "limit": top_k,
        "attributesToHighlight": ["commentary", "transliteration", "topic_heading"],
        "highlightPreTag": "**",
        "highlightPostTag": "**",
        "attributesToRetrieve": [
            "chunk_id", "sthana", "chapter_number", "chapter_title",
            "verse_id", "topic_heading", "sanskrit_text", "transliteration",
            "commentary", "primary_category", "dosha", "roga", "dravya",
            "karma", "content_type", "source_file"
        ]
    }

    # Add hybrid if alpha > 0 (requires embedder to be configured)
    if alpha > 0:
        params["hybrid"] = {
            "semanticRatio": alpha,
            "embedder": "default"
        }

    if filters:
        params["filter"] = " AND ".join(filters)

    result = index.search(query, params)
    return result.get("hits", [])


def kv_search(
    *,
    dosha: str = None,
    roga: str = None,
    dravya: str = None,
    sthana: str = None,
    chapter: int = None,
    book: str = None,
    limit: int = 50
) -> list[dict]:
    """
    Pure filter/key-value search — no text query.
    Good for 'show me all vata recipes' or 'all Nidanasthana chapters'.
    """
    index = get_index()

    filters = []
    if dosha:    filters.append(f'dosha = "{dosha}"')
    if roga:     filters.append(f'roga = "{roga}"')
    if dravya:   filters.append(f'dravya = "{dravya}"')
    if sthana:   filters.append(f'sthana = "{sthana}"')
    if chapter:  filters.append(f'chapter_number = {chapter}')
    if book:     filters.append(f'source_file = "{book}"')

    params = {
        "filter": " AND ".join(filters) if filters else "",
        "limit": limit,
        "sort": ["chapter_number:asc"]
    }

    result = index.search("", params)
    return result.get("hits", [])


def print_results(hits: list[dict], query: str = ""):
    if query:
        print(f"\n=== Results for: '{query}' ({len(hits)} hits) ===\n")
    for i, h in enumerate(hits, 1):
        print(f"{i}. [{h.get('chunk_id')}] {h.get('topic_heading', '')}")
        print(f"   Sthana: {h.get('sthana')}  |  Verse: {h.get('verse_id')}")
        if h.get('dosha'):  print(f"   Dosha: {', '.join(h['dosha'])}")
        if h.get('roga'):   print(f"   Roga: {', '.join(h['roga'])}")
        if h.get('dravya'): print(f"   Dravya: {', '.join(h['dravya'])}")
        comm = h.get('commentary', '')
        if comm:
            print(f"   Commentary: {comm[:150]}{'...' if len(comm)>150 else ''}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="vata dosha treatment")
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--dosha", default=None)
    parser.add_argument("--roga", default=None)
    parser.add_argument("--book", default=None)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    hits = search(
        args.query,
        alpha=args.alpha,
        dosha=args.dosha,
        roga=args.roga,
        book=args.book,
        top_k=args.top_k
    )
    print_results(hits, args.query)
