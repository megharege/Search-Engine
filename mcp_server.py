"""
AyurRAG MCP Server — FastAPI

Endpoints
─────────
GET  /health     liveness
GET  /books      list all books in the corpus
GET  /manifest   MCP tool manifest (Claude Desktop auto-discovery)
POST /search     hybrid / semantic / keyword search
POST /lookup     exact key-value lookup by chunk_id / verse_id / book_id

Run locally:
    uvicorn mcp_server:app --host 0.0.0.0 --port 8000 --reload

In Docker:
    CMD ["uvicorn", "mcp_server:app", "--host", "0.0.0.0", "--port", "8000"]
"""
from __future__ import annotations
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# load model once at server startup (not per-request)
from src.embed import embedder
embedder.load()

from src.search import search_verses, lookup_verse

app = FastAPI(title="AyurRAG MCP Server", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BOOKS = [
    {"book_id": "MN1", "name": "Madhava Nidana - Part 1"},
    {"book_id": "MN2", "name": "Madhava Nidana - Part 2"},
    {"book_id": "SUS", "name": "Sushruta Samhita"},
    {"book_id": "AH",  "name": "Ashtanga Hridaya"},
]

# ── request/response schemas ──────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str = Field(..., description="Clinical query: symptom, disease, treatment, or partial shloka")
    mode: str  = Field("hybrid", description="'hybrid' | 'semantic' | 'keyword'")
    embed_field: str = Field(
        "commentary_embedder",
        description="'commentary_embedder' (search by meaning) or 'transliteration_embedder' (search by verse text)",
    )
    top_k: int = Field(10, ge=1, le=50, description="Max results to return")
    book_id:          Optional[list[str]] = Field(None, description="Filter to book IDs, e.g. ['MN1','SUS']")
    sthana:           Optional[list[str]] = Field(None, description="Filter by sthana (textual division)")
    primary_category: Optional[list[str]] = Field(None, description="Filter by primary_category tag")
    categories_found: Optional[list[str]] = Field(None, description="Filter by category tags")
    chapter_range:    Optional[list[int]] = Field(None, description="[min_chapter, max_chapter] inclusive")


class LookupRequest(BaseModel):
    chunk_id: Optional[str] = Field(None, description="Exact chunk ID, e.g. 'AH_1'")
    verse_id: Optional[str] = Field(None, description="Verse identifier")
    book_id:  Optional[str] = Field(None, description="Book ID to scope results")


# ── endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/books")
def list_books():
    return BOOKS


@app.post("/search")
def search(req: SearchRequest):
    if req.mode not in ("hybrid", "semantic", "keyword"):
        raise HTTPException(400, "mode must be 'hybrid', 'semantic', or 'keyword'")
    try:
        hits = search_verses(
            query            = req.query,
            mode             = req.mode,
            embed_field      = req.embed_field,
            top_k            = req.top_k,
            book_id          = req.book_id,
            sthana           = req.sthana,
            primary_category = req.primary_category,
            categories_found = req.categories_found,
            chapter_range    = req.chapter_range,
        )
        return {"hits": hits, "count": len(hits)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/lookup")
def lookup(req: LookupRequest):
    if not any([req.chunk_id, req.verse_id, req.book_id]):
        raise HTTPException(400, "Provide at least one of: chunk_id, verse_id, book_id")
    try:
        hits = lookup_verse(
            chunk_id = req.chunk_id,
            verse_id = req.verse_id,
            book_id  = req.book_id,
        )
        return {"hits": hits, "count": len(hits)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/manifest")
def manifest():
    """MCP tool manifest — auto-discovered by Claude Desktop and other MCP clients."""
    return {
        "schema_version": "v1",
        "name": "ayur-rag",
        "description": (
            "Search Ayurvedic shlokas across Madhava Nidana (Parts 1 & 2), "
            "Sushruta Samhita, and Ashtanga Hridaya by symptom, disease, or treatment."
        ),
        "tools": [
            {
                "name": "search_verses",
                "description": (
                    "Hybrid semantic + keyword search over Ayurvedic verse commentaries. "
                    "Use this to find shlokas relevant to a symptom, disease, or treatment concept."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query":            {"type": "string"},
                        "mode":             {"type": "string", "enum": ["hybrid", "semantic", "keyword"], "default": "hybrid"},
                        "embed_field":      {"type": "string", "enum": ["commentary_embedder", "transliteration_embedder"], "default": "commentary_embedder"},
                        "top_k":            {"type": "integer", "default": 10},
                        "book_id":          {"type": "array", "items": {"type": "string"}},
                        "sthana":           {"type": "array", "items": {"type": "string"}},
                        "primary_category": {"type": "array", "items": {"type": "string"}},
                        "categories_found": {"type": "array", "items": {"type": "string"}},
                        "chapter_range":    {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    },
                    "required": ["query"],
                },
                "endpoint": {"method": "POST", "path": "/search"},
            },
            {
                "name": "lookup_verse",
                "description": "Exact key-value lookup: fetch a specific chunk by its ID, verse ID, or book.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "verse_id": {"type": "string"},
                        "book_id":  {"type": "string"},
                    },
                },
                "endpoint": {"method": "POST", "path": "/lookup"},
            },
            {
                "name": "list_books",
                "description": "List all books available in the Ayurvedic corpus.",
                "input_schema": {"type": "object", "properties": {}},
                "endpoint": {"method": "GET", "path": "/books"},
            },
        ],
    }
