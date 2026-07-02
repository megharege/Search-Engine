# Ayurveda MCP Server & MeiliSearch Setup

This folder contains the MCP (Model Context Protocol) server and MeiliSearch setup utilities.

## Prerequisites

1. Python 3.10+
2. Dependencies installed: `pip install -r ../requirements.txt`
3. MeiliSearch running (see below)

## Starting MeiliSearch

From the **project root**:

```powershell
.\meilisearch.exe --master-key "ayurveda-dev-key" --db-path "./data.ms" --no-analytics
```

## Running the MCP Server

```powershell
# Standard SSE transport (works with all MCP clients)
python mcp_server.py

# HTTP transport with auth middleware
python mcp_server.py --http
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `search_verses(query, sthana?, primary_category?, limit?)` | Hybrid search across all texts |
| `get_chunk(chunk_id)` | Fetch a single verse by chunk_id |
| `list_texts()` | List all available source books/sthanas |
| `list_categories()` | List all primary categories |

## Setup Utilities

### Creating the Meilisearch Index

If you need to set up the index from scratch (normally handled by `ingest.py` in the project root):

```powershell
python meili_setup.py
```

### Indexing Individual JSONL Files

```powershell
python meili_index.py path/to/file.jsonl --source-file "Book Name"
```

### Testing the Search

```powershell
python test_search.py
```
