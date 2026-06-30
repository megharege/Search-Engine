# Ayurveda MeiliSearch Setup

This folder contains the scripts and instructions to set up a MeiliSearch RAG index for Ayurveda texts.

## Prerequisites

1. Python 3.8+
2. The `meilisearch` Python package installed:
   ```powershell
   pip install meilisearch
   ```
3. MeiliSearch executable (downloaded in this folder as `meilisearch.exe`).

## Starting MeiliSearch

Start the MeiliSearch server with the requested limits. For ~10k total documents, setting a max indexing memory of 200Mb and payload size of 100Mb is sufficient to prevent OOM errors.

```powershell
.\meilisearch.exe --master-key "ayurveda-dev-key" --no-analytics --max-indexing-memory 200Mb --http-payload-size-limit 100Mb
```
*(Keep this terminal running in the background).*

## Setup the Index

Run the setup script to create the `ayurveda` index, configure searchable/filterable attributes, and set up the HuggingFace `intfloat/multilingual-e5-small` embedder.

```powershell
python meili_setup.py
```

## Indexing the Documents

Ensure your JSONL files (`sushruta.jsonl`, `bhavaprakasa.jsonl`, `madhavanidanam.jsonl`, `sharangadhara.jsonl`) are present in this directory (or update the paths below to point to them). Then run:

```powershell
python meili_index.py sushruta.jsonl --source-file "Sushruta Samhita"
python meili_index.py bhavaprakasa.jsonl --source-file "Bhavaprakasa Nighantu"
python meili_index.py madhavanidanam.jsonl --source-file "Madhavanidanam"
python meili_index.py sharangadhara.jsonl --source-file "Sharangadhara Samhita"
```

## Testing the Search

To run a hybrid search query for "vata dosha jwara treatment" (with a `semanticRatio` of 0.5) and print index statistics:

```powershell
python test_search.py
```
