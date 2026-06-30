# 🕉️ Ayurveda Verse Search Engine

A full-stack semantic search engine for classical Ayurvedic texts, powered by **MeiliSearch** with hybrid (keyword + AI semantic) search using HuggingFace embeddings.

Search through **1,080+ verses** across 4 classical Ayurvedic texts with highlighted results, book filters, and multiple search modes.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![MeiliSearch](https://img.shields.io/badge/MeiliSearch-Latest-purple)
![FastAPI](https://img.shields.io/badge/FastAPI-0.138-green?logo=fastapi)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📚 Indexed Texts

| Book | File | Documents |
|---|---|---|
| **Sushruta Samhita** | `sushrut-final_output.jsonl` | 382 |
| **Ashtanga Hridaya** | `ashtanga-hridaya-final_output.jsonl` | 331 |
| **Madhavanisana Pt2** | `B03-madhavanisana-pt2-final_output.jsonl` | 298 |
| **Madhavanisana Pt1** | `B02-madhavanisana-pt1-final_output.jsonl` | 69 |

Each record includes: Sanskrit text, transliteration, commentary, chapter/verse info, topic headings, and category tags.

---

## ✨ Features

- **Hybrid Search** — Combines keyword matching and AI semantic similarity (powered by `intfloat/multilingual-e5-small`)
- **Three Search Modes** — Hybrid, Semantic-only, and Keyword-only
- **Book Filters** — Filter results by any combination of the 4 texts
- **Highlighted Results** — Matching terms highlighted in commentary and transliteration
- **Diacritics-Aware** — Typo tolerance disabled on Sanskrit/transliteration fields so `ā` ≠ `a`
- **Premium Dark UI** — Glassmorphism, gradients, Google Fonts (Outfit + Inter), and micro-animations
- **SEO Optimized** — Semantic HTML5, proper meta tags, heading hierarchy

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Frontend   │────▶│  FastAPI     │────▶│   MeiliSearch    │
│  (HTML/JS)  │     │  (api.py)    │     │   port 7700      │
│  port 8000  │     │  /api/search │     │   HuggingFace    │
└─────────────┘     └──────────────┘     │   Embedder       │
                                         └──────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Git

### 1. Clone the repository

```bash
git clone https://github.com/megharege/search-engine.git
cd search-engine
```

### 2. Install Python dependencies

```bash
pip install meilisearch fastapi uvicorn requests
```

### 3. Download MeiliSearch

**Windows:**
```powershell
curl.exe -L -o ayurveda_meili/meilisearch.exe https://github.com/meilisearch/meilisearch/releases/latest/download/meilisearch-windows-amd64.exe
```

**Linux/macOS:**
```bash
curl -L https://install.meilisearch.com | sh
mv meilisearch ayurveda_meili/
```

### 4. Start MeiliSearch

```bash
cd ayurveda_meili
./meilisearch --master-key "ayurveda-dev-key" --no-analytics --max-indexing-memory 200Mb --http-payload-size-limit 100Mb
```

> Keep this terminal running in the background.

### 5. Setup the index (new terminal)

```bash
cd ayurveda_meili
python meili_setup.py
```

This creates the `ayurveda` index with:
- Searchable attributes: `topic_heading`, `transliteration`, `commentary`, `sanskrit_text`, `chapter_title`, `sthana`
- Filterable attributes: `source_file`, `sthana`, `chapter_number`, `primary_category`, `categories_found`
- HuggingFace embedder: `intfloat/multilingual-e5-small`
- Typo tolerance disabled on `sanskrit_text` and `transliteration`

### 6. Index the 4 books

```bash
python meili_index.py "../B02-madhavanisana-pt1-final_output.jsonl" --source-file "Madhavanisana Pt1"
python meili_index.py "../B03-madhavanisana-pt2-final_output.jsonl" --source-file "Madhavanisana Pt2"
python meili_index.py "../ashtanga-hridaya-final_output.jsonl" --source-file "Ashtanga Hridaya"
python meili_index.py "../sushrut-final_output.jsonl" --source-file "Sushruta Samhita"
```

### 7. Launch the web app

```bash
python api.py
```

Open **http://localhost:8000** in your browser 🎉

---

## 📁 Project Structure

```
search-engine/
├── README.md                          # This file
├── app.py                             # Legacy Streamlit UI (optional)
├── 1_tag_extractor.py                 # Tag extraction pipeline
├── 2_meili_setup.py                   # Older setup script
├── 3_meili_index.py                   # Older indexing script
├── 4_hybrid_search.py                 # Hybrid search experiments
├── 5_reranker.py                      # Reranking pipeline
├── 6_pipeline_runner.py               # Full pipeline runner
├── 7_qdrant_build.py                  # Qdrant vector DB builder
├── meili_setup.py                     # Root-level MeiliSearch setup
├── meili_index.py                     # Root-level indexing script
│
├── B02-madhavanisana-pt1-final_output.jsonl   # Book data
├── B03-madhavanisana-pt2-final_output.jsonl   # Book data
├── ashtanga-hridaya-final_output.jsonl        # Book data
├── sushrut-final_output.jsonl                 # Book data
│
└── ayurveda_meili/                    # Main web app
    ├── api.py                         # FastAPI backend
    ├── meili_setup.py                 # Index configuration
    ├── meili_index.py                 # Bulk indexer with task polling
    ├── test_search.py                 # Search verification script
    ├── README.md                      # Setup instructions
    └── public/                        # Frontend
        ├── index.html                 # SEO-optimized HTML
        ├── styles.css                 # Premium dark theme CSS
        └── script.js                  # Search logic & rendering
```

---

## 🔍 Search Modes

| Mode | Description |
|---|---|
| **Hybrid** | Combines keyword relevance + semantic similarity (50/50 ratio) |
| **Semantic** | Pure AI vector search using multilingual embeddings |
| **Keyword** | Traditional full-text search with BM25-style ranking |

---

## ⚙️ Configuration

| Parameter | Value | Rationale |
|---|---|---|
| Embedding Model | `intfloat/multilingual-e5-small` | Multilingual support for Sanskrit + English |
| Max Indexing Memory | 200 MB | Sufficient for ~10k documents |
| HTTP Payload Limit | 100 MB | Handles large batch uploads |
| Typo Tolerance | Disabled on Sanskrit fields | Diacritics (`ā`, `ī`, `ū`) are semantically important |
| Batch Size | 500 documents | Balanced memory usage and speed |

---

## 📄 Data Format

Each JSONL record follows this schema:

```json
{
  "chunk_id": "AH9",
  "sthana": "Sutrasthana",
  "chapter_number": 1,
  "chapter_title": "Ayushkameeya Adhyaya",
  "verse_id": "4.5-5",
  "topic_heading": "Branches of Ayurveda",
  "sanskrit_text": "...",
  "transliteration": "...",
  "commentary": "...",
  "source_lines": "42-58",
  "categories_found": ["general"],
  "primary_category": "general"
}
```

---

## 🛠️ Tech Stack

- **Search Engine**: [MeiliSearch](https://www.meilisearch.com/) — fast, typo-tolerant full-text search with vector support
- **Embeddings**: [HuggingFace intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) — multilingual semantic embeddings
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) — modern async Python web framework
- **Frontend**: Vanilla HTML/CSS/JS — no framework overhead, fast loading
- **Typography**: [Google Fonts](https://fonts.google.com/) — Outfit + Inter

---

## 📜 License

MIT License
