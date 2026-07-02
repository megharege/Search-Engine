# 🌿 Ayurveda Search Engine

A powerful Ayurvedic verse search engine with **Hybrid**, **Semantic**, and **Keyword** search across classical texts — Sushruta Samhita, Ashtanga Hridaya, and Madhavanidanam.

Built with [Meilisearch](https://www.meilisearch.com/) for fast full-text + vector search, [Streamlit](https://streamlit.io/) for the AI-powered search UI, and [FastAPI](https://fastapi.tiangolo.com/) for the website frontend.

---

## Features

- **Hybrid Search** — Combines keyword matching with semantic vector similarity for the best results
- **Semantic Search** — Find verses by meaning, not just exact words (powered by `intfloat/multilingual-e5-small` embeddings)
- **Keyword Search** — Traditional full-text search with typo tolerance
- **LLM Re-ranking** (optional) — Re-ranks results using Gemini or Claude for higher relevance
- **MCP Server** — Model Context Protocol integration for AI assistants
- **Two Frontends** — Streamlit app with AI model + FastAPI-served website
- **Book Filtering** — Filter results by source text
- **Search Memory** — Persistent search history in the website UI

---

## Prerequisites

1. **Python 3.10+**
2. **Meilisearch binary** — Download from [Meilisearch releases](https://github.com/meilisearch/meilisearch/releases) and place `meilisearch.exe` in the project root
3. **Git** (to clone the repo)

---

## Quick Start (Windows)

```powershell
# 1. Clone the repository
git clone https://github.com/megharege/search-engine.git
cd search-engine

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Copy and edit environment variables
copy .env.example .env
# Edit .env with your API keys (optional — search works without them)

# 4. Download meilisearch.exe into the project root
# https://github.com/meilisearch/meilisearch/releases

# 5. Launch everything with one click
# Double-click "Start Ayurveda Explorer.bat"
# OR run from terminal:
.\Start Ayurveda Explorer.bat
```

The batch file will:
1. Start Meilisearch on `http://localhost:7700`
2. Run data ingestion (loads embeddings into the index)
3. Start the FastAPI website on `http://localhost:8000`
4. Start the Streamlit app on `http://localhost:8501` (opens automatically)

---

## Manual Setup (All Platforms)

### Step 1: Start Meilisearch

```bash
./meilisearch --master-key "ayurveda-dev-key" --db-path "./data.ms" --no-analytics
```

### Step 2: Ingest Data

```bash
python ingest.py
```

This loads `Final data/merged_books_with_embeddings.jsonl` (1081 verses with pre-computed 384-dim embeddings) into the Meilisearch index.

### Step 3: Run the Streamlit App

```bash
streamlit run app.py
```
Opens at `http://localhost:8501` — supports all three search modes with an AI embedding model loaded in-process.

### Step 4 (Optional): Run the FastAPI Website

```bash
cd ayurveda_meili
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```
Opens at `http://localhost:8000` — a standalone HTML/JS/CSS frontend.

### Step 5 (Optional): Run the MCP Server

```bash
cd "Meili MCP Server"
python mcp_server.py          # SSE transport (default)
python mcp_server.py --http   # HTTP transport with auth middleware
```

---

## Project Structure

```
Search Engine/
├── app.py                    # Streamlit search UI (main frontend)
├── search_core.py            # Core search logic (Meilisearch + LLM re-ranking)
├── ingest.py                 # Data ingestion script
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── Start Ayurveda Explorer.bat  # One-click Windows launcher
│
├── Final data/               # Source data & embeddings
│   ├── merged_books_with_embeddings.jsonl  # 1081 verses with pre-computed vectors
│   ├── generate_embeddings.py              # Script to regenerate embeddings
│   ├── ashtanga-hridaya-final_output.jsonl # Source: Ashtanga Hridaya
│   ├── sushrut-final_output.jsonl          # Source: Sushruta Samhita
│   ├── B02-madhavanisana-pt1-final_output.jsonl  # Source: Madhavanisana Pt1
│   └── B03-madhavanisana-pt2-final_output.jsonl  # Source: Madhavanisana Pt2
│
├── ayurveda_meili/           # FastAPI website backend
│   ├── api.py                # FastAPI app serving search API + static files
│   └── public/               # Website frontend (HTML/JS/CSS)
│
├── Meili MCP Server/         # MCP server for AI assistant integration
│   ├── mcp_server.py         # FastMCP server with auth middleware
│   ├── search_core.py        # Search logic (shared with root)
│   ├── meili_setup.py        # Meilisearch index setup utility
│   ├── meili_index.py        # Manual document indexing utility
│   └── test_search.py        # Search test script
│
├── Website/                  # Standalone static website (reference copy)
│   ├── index.html
│   ├── script.js
│   └── styles.css
│
└── Pipeline/                 # Data processing pipeline scripts
    ├── 1_tag_extractor.py
    ├── 2_meili_setup.py
    ├── ...
    └── README.md
```

---

## Search Modes Explained

| Mode | How It Works | Best For |
|------|-------------|----------|
| **Hybrid** | 50/50 blend of keyword + semantic | General queries |
| **Semantic** | 100% vector similarity search | Meaning-based queries (e.g., "treatment for fever") |
| **Keyword** | Traditional full-text search | Exact terms, Sanskrit words, specific verse IDs |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MEILI_MASTER_KEY` | Yes | Master key for Meilisearch (default: `ayurveda-dev-key`) |
| `MCP_AUTH_TOKEN` | No | Bearer token for MCP server auth |
| `GOOGLE_API_KEY` | No | Gemini API key for LLM re-ranking |
| `ANTHROPIC_API_KEY` | No | Anthropic API key for LLM re-ranking |

---

## Regenerating Embeddings

If you need to regenerate the embedding vectors (e.g., after adding new texts):

```bash
cd "Final data"
python generate_embeddings.py
```

This uses `intfloat/multilingual-e5-small` (384 dimensions) and writes `merged_books_with_embeddings.jsonl`.

---

## Contributing

Feel free to open issues or submit pull requests for any enhancements or bug fixes.
