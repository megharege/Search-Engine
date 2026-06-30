from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import meilisearch
import uvicorn
from typing import List

app = FastAPI(title="Ayurveda Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

meili_client = meilisearch.Client("http://localhost:7700", "ayurveda-dev-key")
index = meili_client.index("ayurveda")

class SearchRequest(BaseModel):
    query: str
    books: List[str]
    mode: str = "Hybrid" # Hybrid, Semantic, Keyword
    limit: int = 20

@app.post("/api/search")
def search(req: SearchRequest):
    params = {
        "limit": req.limit,
        "attributesToHighlight": ["commentary", "transliteration", "topic_heading"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
    }

    if req.mode == "Hybrid":
        params["hybrid"] = {"semanticRatio": 0.5, "embedder": "default"}
    elif req.mode == "Semantic":
        params["hybrid"] = {"semanticRatio": 1.0, "embedder": "default"}
        
    if req.books:
        book_clause = " OR ".join([f'source_file = "{b}"' for b in req.books])
        params["filter"] = f"({book_clause})"

    results = index.search(req.query, params)
    return {"hits": results.get("hits", []), "processingTimeMs": results.get("processingTimeMs", 0)}

app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
