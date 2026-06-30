# Ayurveda Verse Search — Pipeline README

A hybrid search engine for classical Ayurvedic texts (Sushruta Samhita, Bhavaprakasa
Nighantu, Madhavanidanam, Sharangadhara Samhita, Astanga Hridaya) combining keyword
search, semantic vector search, and LLM-based re-ranking.

---

## 1. What this is

Given a natural-language query like *"vata dosha fever treatment"*, the system
returns the actual relevant Sanskrit verses — with transliteration, English
commentary, and source metadata — ranked by relevance, with filters for book,
sthana, chapter, and category.

---

## 2. Architecture

```
JSONL (source data)
      │
      ▼
┌─────────────┐
│   Tagging   │  offline, one-time — LLM extracts dosha/roga/dravya/karma tags
└─────────────┘
      │
      ▼
┌─────────────┐
│  Embedding  │  multilingual-e5-small → 384-dim vector per chunk
└─────────────┘
      │
      ▼
┌─────────────────────────────┐
│   Indexing (choose one)     │
│  ┌────────────┐ ┌─────────┐ │
│  │ MeiliSearch│ │ Qdrant  │ │
│  │ BM25+vector│ │ vector  │ │
│  └────────────┘ └─────────┘ │
└─────────────────────────────┘
      │
      ▼
┌─────────────┐
│   Query +   │  filters (book/sthana/chapter) + hybrid search (alpha blend)
│   Filter    │
└─────────────┘
      │
      ▼
┌─────────────┐
│  Re-ranking │  LLM scores top-20 candidates 0–10 for true relevance
└─────────────┘
      │
      ▼
┌─────────────┐
│   UI cards  │  Streamlit — Sanskrit, transliteration, commentary, tags, score
└─────────────┘
```

---

## 3. Data format

Each line in the source JSONL is one verse/chunk:

```json
{
  "chunk_id": "AH9",
  "sthana": "Sutrasthana",
  "chapter_number": 1,
  "chapter_title": "Ayushkameeya Adhyaya",
  "verse_id": "4.5-5",
  "topic_heading": "5 - Branches of Ayurveda",
  "sanskrit_text": "...",
  "transliteration": "...",
  "commentary": "...",
  "source_lines": "42-58",
  "categories_found": ["general"],
  "primary_category": "general"
}
```

---

## 4. Pipeline stages explained

### 4.1 Tagging (offline, one-time)
An LLM (Claude) reads each chunk's commentary and extracts structured tags —
dosha, roga (disease), dravya (herb/substance), karma (therapeutic action) —
that may be implied but not literally stated. These get written back into the
JSONL as new fields and become additional filter options. This step runs once,
in batch, before indexing.

### 4.2 Embedding
`intfloat/multilingual-e5-small` converts each chunk's `topic_heading +
transliteration + commentary` into a 384-dimensional vector — a numeric
representation of meaning that allows similarity comparison between any two
texts via cosine distance. It's multilingual, so it handles both Sanskrit
transliteration and English commentary reasonably well in the same space.

### 4.3 Indexing — two backend options

**MeiliSearch** — one engine, two scoring methods combined:
- *BM25 (keyword)*: classic term-frequency relevance scoring, no understanding
  of meaning — rewards exact and near-exact word matches.
- *Vector search*: documents and queries are embedded the same way at index/query
  time; nearest-neighbor vectors are retrieved.
- `semanticRatio` (the "alpha" param) linearly blends the two: 0 = pure keyword,
  1 = pure semantic, 0.5 = balanced hybrid (default).

**Qdrant** — pure vector database, no keyword layer. Embeddings are computed
externally via `sentence-transformers` and uploaded as points with metadata
payloads. Uses HNSW (approximate nearest neighbor) for fast retrieval at scale.

### 4.4 Filtering
Both engines support metadata filters (`sthana = "Sutrasthana" AND
chapter_number <= 10`) applied as a hard constraint on the candidate set,
separate from relevance scoring. This powers the book/sthana/chapter/category
sidebar filters in the UI.

### 4.5 Re-ranking (online, per-query)
Search engines optimize for statistical match (term overlap, vector distance),
not for "is this the clinically best answer." After retrieving the top ~20
candidates, a second LLM call (Gemini or Claude) reads each one against the
actual query and assigns a relevance score with reasoning, re-ordering down to
the best 5. This is the standard retrieve-then-rerank pattern used in
production RAG systems — it trades a bit of latency for materially better
top results.

### 4.6 UI
Streamlit renders the filter sidebar and verse-card results. It's a thin
client — all logic lives in the search/rerank calls; the UI just builds filter
strings, calls the backend's `/search` API, and displays the JSON response.

---

## 5. Setup

```bash
pip install meilisearch streamlit sentence-transformers qdrant-client anthropic google-generativeai

export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."          # optional, for Gemini re-ranking

curl -L https://install.meilisearch.com | sh
./meilisearch --master-key='ayurveda-dev-key' --no-analytics --max-indexing-memory 2Gb
```

---

## 6. Run order

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `python 1_tag_extractor.py --input corpus.jsonl` | Tag chunks with dosha/roga/dravya/karma |
| 2 | `python meili_setup.py` | Configure index, embedder, performance settings |
| 3 | `python meili_index.py --input <book>.jsonl --source-file "<Book Name>"` | Index each book (run 4x) |
| 4 | `python 4_hybrid_search.py "<query>" --alpha 0.5` | Test search |
| 5 | `python 5_reranker.py "<query>" --summarize` | Re-rank + clinical summary |
| 6 | `streamlit run app.py --server.port 8501` | Launch UI |

For Qdrant instead of MeiliSearch:
```bash
docker run -p 6333:6333 qdrant/qdrant
python 7_qdrant_build.py --index --input corpus_tagged.jsonl
python 7_qdrant_build.py --query "pitta herbs"
```

---

## 7. Search modes

| Mode | alpha / semanticRatio | Best for |
|------|------------------------|----------|
| Keyword | 0.0 | Exact herb/disease/Sanskrit term lookup |
| Hybrid | 0.5 | General queries — default |
| Semantic | 1.0 | Conceptual/meaning-based queries |
| Filter only | n/a | Browsing by dosha/book/sthana with no text query |

---

## 8. Performance notes

- Typo tolerance is disabled on `transliteration`/`sanskrit_text` — diacritics
  (ā vs a, ṣ vs s) carry meaning in IAST, so MeiliSearch's automatic typo
  correction is turned off for these fields to avoid false matches.
- `maxTotalHits` capped at 1000 to prevent slow deep pagination.
- Indexing batches are submitted concurrently then waited on together, rather
  than sequentially — significantly faster for multi-book uploads.
- `byWord` proximity precision is used instead of `byAttribute` — faster for
  short verse/commentary fields.
- Streamlit caches the search client connection (`@st.cache_resource`) so it
  isn't re-established on every UI rerun.

---

## 9. File structure

```
1_tag_extractor.py     Offline tagging via Claude (dosha/roga/dravya/karma)
meili_setup.py          MeiliSearch index config + embedder + perf tuning
meili_index.py           Bulk upload JSONL → MeiliSearch (per book)
4_hybrid_search.py      Keyword / semantic / hybrid search functions
5_reranker.py            LLM re-ranking + clinical summary generation
7_qdrant_build.py        Parallel pure-vector build using Qdrant
app.py                   Streamlit UI — filters, search, verse cards
ANTIGRAVITY_PROMPT.txt   Prompt to bootstrap MeiliSearch setup in Antigravity
```
