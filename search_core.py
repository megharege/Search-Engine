import os
from dotenv import load_dotenv
load_dotenv()

import json
import logging
import meilisearch

# Optional LLM for re-ranking
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Configuration
MEILI_URL = os.environ.get("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.environ.get("MEILI_MASTER_KEY", "ayurveda-dev-key")
MEILI_INDEX = "ayurveda"

# Clients
_meili_client = None

def get_meili():
    global _meili_client
    if not _meili_client:
        _meili_client = meilisearch.Client(MEILI_URL, MEILI_MASTER_KEY)
    return _meili_client

def fetch_chunk_by_id(chunk_id: str) -> dict:
    """Fetch the full record for a single chunk by its chunk_id from Meilisearch."""
    try:
        index = get_meili().index(MEILI_INDEX)
        return index.get_document(chunk_id)
    except Exception as e:
        logging.error(f"Error fetching chunk {chunk_id}: {e}")
        return {}

def get_available_texts() -> list[str]:
    """List all source book titles / sthanas available in the index."""
    try:
        index = get_meili().index(MEILI_INDEX)
        res = index.search("", {"facets": ["source_file", "sthana"], "limit": 0})
        facets = res.get("facetDistribution", {})
        books = list(facets.get("source_file", {}).keys())
        sthanas = list(facets.get("sthana", {}).keys())
        return list(set(books + sthanas))
    except Exception as e:
        logging.error(f"Error fetching available texts: {e}")
        return []

def get_available_categories() -> list[str]:
    """List all distinct primary_category values available in the index."""
    try:
        index = get_meili().index(MEILI_INDEX)
        res = index.search("", {"facets": ["primary_category"], "limit": 0})
        facets = res.get("facetDistribution", {})
        return list(facets.get("primary_category", {}).keys())
    except Exception as e:
        logging.error(f"Error fetching available categories: {e}")
        return []


def hybrid_search(query: str, sthana: str | None = None, primary_category: str | None = None, limit: int = 10, mode: str = "Hybrid", embed_model=None) -> list[dict]:
    """
    Hybrid keyword + semantic search over classical Ayurvedic texts.
    Uses MeiliSearch for native hybrid search.
    Re-ranks top results if LLM API keys are present.
    embed_model: pre-loaded SentenceTransformer instance (passed in for caching/latency)
    """
    query_vector = None
    if mode in ["Hybrid", "Semantic"] and embed_model is not None:
        try:
            import torch
            with torch.no_grad():
                query_vector = embed_model.encode(
                    query,
                    show_progress_bar=False,
                    convert_to_numpy=True
                ).tolist()
        except Exception as e:
            logging.error(f"Error generating query embedding: {e}")
            
    results = _meili_search(query, sthana, primary_category, limit=limit*2, mode=mode, vector=query_vector)
    
    # Optional LLM Re-ranking
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
        results = _llm_rerank(query, results)
        
    # Pass through ALL fields from Meilisearch (needed by Streamlit UI & MCP)
    # Only normalize the 'score' field for consistent downstream use
    formatted_results = []
    for r in results[:limit]:
        hit = dict(r)  # shallow copy to avoid mutating originals
        # Normalize score: prefer LLM-assigned score, then _rankingScore, then _semanticScore
        if "score" not in hit:
            hit["score"] = hit.get("_rankingScore", hit.get("_semanticScore", 0.0))
        formatted_results.append(hit)
        
    # Ensure final output is strictly sorted by the normalized score descending
    formatted_results.sort(key=lambda x: x["score"], reverse=True)
    return formatted_results

def _meili_search(query: str, sthana: str | None, primary_category: str | None, limit: int, mode: str = "Hybrid", vector: list[float] | None = None) -> list[dict]:
    try:
        index = get_meili().index(MEILI_INDEX)
        filters = []
        if sthana:
            filters.append(f'sthana = "{sthana}"')
        if primary_category:
            filters.append(f'primary_category = "{primary_category}"')
            
        params = {
            "limit": limit,
            "showRankingScore": True
        }
        
        if mode in ["Hybrid", "Semantic"] and vector:
            params["vector"] = vector
            params["hybrid"] = {
                "embedder": "default",
                "semanticRatio": 0.5 if mode == "Hybrid" else 1.0
            }
            
        if filters:
            params["filter"] = " AND ".join(filters)
            
        res = index.search(query, params)
        return res.get("hits", [])
    except Exception as e:
        logging.error(f"Meilisearch error: {e}")
        return []

def _llm_rerank(query: str, hits: list[dict]) -> list[dict]:
    RERANK_PROMPT = f"""You are a senior Ayurveda scholar and physician.
A user searched for: "{query}"
Below are candidate shlokas. Score each 0-10 for relevance.
Return ONLY a JSON array: [{{"chunk_id": "...", "score": 8}}]

Candidates:
"""
    candidates = []
    for h in hits:
        candidates.append({
            "chunk_id": h.get("chunk_id"),
            "topic": h.get("topic_heading", ""),
            "text": h.get("commentary", "")[:300]
        })
    prompt = RERANK_PROMPT + json.dumps(candidates, ensure_ascii=False)
    
    scores = {}
    try:
        if GEMINI_AVAILABLE and os.environ.get("GOOGLE_API_KEY"):
            genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
            model = genai.GenerativeModel("gemini-2.0-flash")
            resp = model.generate_content(prompt)
            raw = resp.text.strip()
        elif ANTHROPIC_AVAILABLE and os.environ.get("ANTHROPIC_API_KEY"):
            client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            resp = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.content[0].text.strip()
        else:
            return hits
            
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed_scores = json.loads(raw.strip())
        scores = {s["chunk_id"]: float(s["score"]) for s in parsed_scores}
    except Exception as e:
        logging.error(f"LLM Rerank error: {e}")
        return hits
        
    for h in hits:
        # Fall back to Meilisearch ranking score if LLM missed this chunk
        original_score = h.get("_rankingScore", h.get("_semanticScore", 0.0))
        # Optional: Normalize LLM 0-10 score to 0-1 scale if needed, or leave as is. 
        # Meilisearch scores are 0-1.
        llm_score = scores.get(h.get("chunk_id"))
        
        if llm_score is not None:
            # LLM gave a score (0-10), normalize it to 0-1 so it's comparable
            h["score"] = llm_score / 10.0
        else:
            h["score"] = original_score
            
    return sorted(hits, key=lambda x: x["score"], reverse=True)
