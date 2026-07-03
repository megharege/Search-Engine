# AyurRAG

Hybrid semantic + keyword search over Ayurvedic shlokas.  
Corpus: Madhava Nidana (Parts 1 & 2), Sushruta Samhita, Ashtanga Hridaya.

---

## Pipeline overview

```
data/raw/*.jsonl
      │
      ▼ Step 1: python pipeline.py --steps 1
data/combined.jsonl          (all 4 books merged, 1378 chunks)
      │
      ▼ Step 2: python pipeline.py --steps 2
data/embeddings.npz          (1378 × 1024 × 2 fields, float32)
      │
      ▼ Step 3: python pipeline.py --steps 3   (needs Meilisearch running)
Meilisearch index            (hybrid search ready)
      │
      ├── streamlit run app.py          (local UI)
      └── uvicorn mcp_server:app ...    (MCP/REST API)
```

---

## Local setup (Windows, RTX 4050)

```powershell
# 1. create venv
python -m venv rag
.\rag\Scripts\Activate.ps1

# 2. install CUDA torch FIRST (never put torch in requirements.txt)
pip install torch --index-url https://download.pytorch.org/whl/cu121

# 3. install everything else
pip install -r requirements.txt
```

---

## Step-by-step run

### Step 1 — Combine books
```powershell
python pipeline.py --steps 1
# Output: data/combined.jsonl  (1378 chunks)
```

### Step 2 — Generate embeddings
```powershell
python pipeline.py --steps 2
# Output: data/embeddings.npz  (transliteration + commentary vectors)
# Takes ~2-3 min on RTX 4050. Re-run is instant if combined.jsonl unchanged.
```

### Step 3 — Ingest into Meilisearch
Start Meilisearch in a separate terminal (keep it open):
```powershell
.\meilisearch.exe --master-key "localdevkey"
```

Then ingest:
```powershell
$env:MEILI_MASTER_KEY = "localdevkey"
python pipeline.py --steps 3
```

Or run all 3 steps at once:
```powershell
$env:MEILI_MASTER_KEY = "localdevkey"
python pipeline.py
```

---

## Streamlit UI (local test)
```powershell
$env:MEILI_MASTER_KEY = "localdevkey"
streamlit run app.py
# Opens http://localhost:8501
```

---

## MCP server (local test)
```powershell
$env:MEILI_MASTER_KEY = "localdevkey"
uvicorn mcp_server:app --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs  
MCP manifest: http://localhost:8000/manifest

### Example search call
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "excessive thirst frequent urination", "mode": "hybrid", "top_k": 5}'
```

### Example lookup call
```bash
curl -X POST http://localhost:8000/lookup \
  -H "Content-Type: application/json" \
  -d '{"chunk_id": "AH_1"}'
```

---

## Docker (production)

> **Before building**: Steps 1 and 2 must have run locally so that  
> `data/combined.jsonl` and `data/embeddings.npz` exist —  
> the Docker image bakes them in (no GPU needed at build time).

```powershell
# 1. copy .env.example → .env (edit the key if needed)
copy .env.example .env

# 2. build and start all 3 services
docker compose up --build
```

Services:
| Container     | Port | What it does                        |
|---------------|------|-------------------------------------|
| `ayur_meili`  | 7700 | Meilisearch (persisted volume)      |
| `ayur_mcp`    | 8000 | FastAPI MCP server + REST API       |
| `ayur_ui`     | 8501 | Streamlit search UI                 |

GPU is passed through to `ayur_mcp` and `ayur_ui` via nvidia device reservation.  
Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) installed.

---

## Adding a new book

1. Drop its JSONL into `data/raw/`
2. Add its entry to `BOOKS` in `src/combine.py` and `mcp_server.py`
3. Re-run the pipeline:
   ```powershell
   python pipeline.py --force-embed
   python pipeline.py --steps 3
   ```
   (Or just `python pipeline.py --force-embed` which does all 3.)

---

## Project layout

```
data/raw/            4 raw JSONL files (source of truth)
data/combined.jsonl  merged output of Step 1
data/embeddings.npz  embedding output of Step 2

src/combine.py       Step 1: merge raw files → combined.jsonl
src/embed.py         Step 2: Harrier embeddings → embeddings.npz
src/ingest_meili.py  Step 3: load into Meilisearch
src/search.py        search/lookup helpers (shared by app + MCP server)

pipeline.py          CLI runner: steps 1→2→3
app.py               Streamlit UI
mcp_server.py        FastAPI MCP server

Dockerfile
docker-compose.yml
requirements.txt         (local dev, torch excluded)
requirements.docker.txt  (Docker, torch excluded — in base image)
.streamlit/config.toml   (disables file-watcher log spam)
```
