"""
Search helpers — shared by Streamlit app and MCP server.
All Meilisearch calls go through here.
"""
from __future__ import annotations
import json, os
import meilisearch
from src.embed import embedder

MEILI_URL = os.environ.get("MEILI_URL",       "http://127.0.0.1:7700")
MEILI_KEY = os.environ.get("MEILI_MASTER_KEY", "")
INDEX     = "ayur_chunks"

_MODE_RATIO = {"keyword": 0.0, "hybrid": 0.5, "semantic": 1.0}


def get_index() -> meilisearch.Index:
    client = meilisearch.Client(MEILI_URL, MEILI_KEY or None)
    return client.index(INDEX)


def build_filter(
    book_id:          list[str] | None = None,
    sthana:           list[str] | None = None,
    primary_category: list[str] | None = None,
    categories_found: list[str] | None = None,
    chapter_range:    list[int] | None = None,
) -> str | None:
    clauses = []
    if book_id:
        vals = ", ".join(json.dumps(v) for v in book_id)
        clauses.append(f"book_id IN [{vals}]")
    if sthana:
        vals = ", ".join(json.dumps(v) for v in sthana)
        clauses.append(f"sthana IN [{vals}]")
    if primary_category:
        vals = ", ".join(json.dumps(v) for v in primary_category)
        clauses.append(f"primary_category IN [{vals}]")
    if categories_found:
        vals = ", ".join(json.dumps(v) for v in categories_found)
        clauses.append(f"categories_found IN [{vals}]")
    if chapter_range and len(chapter_range) == 2:
        lo, hi = chapter_range
        clauses.append(f"chapter_number >= {lo} AND chapter_number <= {hi}")
    return " AND ".join(clauses) if clauses else None


def search_verses(
    query:            str,
    mode:             str = "hybrid",
    embed_field:      str = "commentary_embedder",
    top_k:            int = 10,
    book_id:          list[str] | None = None,
    sthana:           list[str] | None = None,
    primary_category: list[str] | None = None,
    categories_found: list[str] | None = None,
    chapter_range:    list[int] | None = None,
) -> list[dict]:
    index  = get_index()
    vector = embedder.encode_query(query).tolist()
    params: dict = {
        "hybrid": {"semanticRatio": _MODE_RATIO.get(mode, 0.5), "embedder": embed_field},
        "vector": vector,
        "limit":  top_k,
    }
    f = build_filter(book_id, sthana, primary_category, categories_found, chapter_range)
    if f:
        params["filter"] = f
    result = get_index().search(query, params)
    return result["hits"]


def lookup_verse(
    chunk_id: str | None = None,
    verse_id: str | None = None,
    book_id:  str | None = None,
) -> list[dict]:
    if not any([chunk_id, verse_id, book_id]):
        return []
    clauses = []
    if chunk_id: clauses.append(f'chunk_id = "{chunk_id}"')
    if verse_id: clauses.append(f'verse_id = "{verse_id}"')
    if book_id:  clauses.append(f'book_id  = "{book_id}"')
    result = get_index().search("", {"filter": " AND ".join(clauses), "limit": 50})
    return result["hits"]
