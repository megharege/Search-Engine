import os
import glob
import json
import time
import logging
from dotenv import load_dotenv
load_dotenv()
from meilisearch import Client as MeiliClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MEILI_URL = os.environ.get("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.environ.get("MEILI_MASTER_KEY", "ayurveda-dev-key")
MEILI_INDEX = "ayurveda"

MODEL_NAME = "intfloat/multilingual-e5-small"

def get_meili_client():
    return MeiliClient(MEILI_URL, MEILI_MASTER_KEY)

def setup_meilisearch(chunks: list[dict]):
    logging.info("Setting up MeiliSearch...")
    ms = get_meili_client()
    
    try:
        ms.update_experimental_features({"vectorStore": True})
        logging.info("Enabled experimental vectorStore feature.")
    except Exception as e:
        logging.warning(f"Failed to enable experimental features via API (might already be enabled): {e}")

    # Ensure index exists
    try:
        ms.get_index(MEILI_INDEX)
        logging.info("Meilisearch index exists")
    except:
        task = ms.create_index(MEILI_INDEX, {'primaryKey': 'chunk_id'})
        wait_for_meili(ms, task.task_uid)
        logging.info("Meilisearch index created")
        
    idx = ms.index(MEILI_INDEX)
    
    # Update settings
    wait_for_meili(ms, idx.update_searchable_attributes([
        'topic_heading','transliteration','commentary',
        'chapter_title','sanskrit_text','sthana','roga','dravya'
    ]).task_uid)

    wait_for_meili(ms, idx.update_filterable_attributes([
        'sthana','chapter_number','primary_category',
        'dosha','roga','dravya','karma','content_type','source_file'
    ]).task_uid)
    
    # Set embedders (Meilisearch 1.9+ supports it)
    try:
        wait_for_meili(ms, idx.update_embedders({
            'default': {
                'source': 'userProvided',
                'dimensions': 384
            }
        }).task_uid)
    except Exception as e:
        logging.warning(f"Could not set Meili embedder (might not be supported on this version): {e}")

    # Clean chunk_ids and list fields
    for c in chunks:
        c['chunk_id'] = str(c['chunk_id']).replace('.','_').replace('/','_')
        for field in ['dosha','roga','dravya','karma']:
            if not isinstance(c.get(field), list):
                c[field] = []

    # Upload
    logging.info(f"Uploading {len(chunks)} chunks to Meilisearch...")
    BATCH = 500
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i+BATCH]
        wait_for_meili(ms, idx.add_documents(batch, primary_key='chunk_id').task_uid)
        logging.info(f"  Meili uploaded {min(i+BATCH, len(chunks))}/{len(chunks)}")
        
    logging.info(f"Meilisearch setup complete. Docs: {idx.get_stats().number_of_documents}")

def wait_for_meili(ms, task_uid):
    for _ in range(120):
        t = ms.get_task(task_uid)
        if t.status == 'succeeded': return t
        if t.status == 'failed': raise RuntimeError(t.error)
        time.sleep(1)

def main():
    # Resolve paths relative to the script's own directory (not CWD)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Look for the embeddings file in multiple locations
    candidates = [
        os.path.join(script_dir, "merged_books_with_embeddings.jsonl"),
        os.path.join(script_dir, "Final data", "merged_books_with_embeddings.jsonl"),
    ]
    
    jsonl_file = None
    for path in candidates:
        if os.path.exists(path):
            jsonl_file = path
            break
    
    if not jsonl_file:
        logging.error(
            "merged_books_with_embeddings.jsonl not found. "
            "Checked:\n  " + "\n  ".join(candidates) + "\n"
            "Run 'python Final data/generate_embeddings.py' first to generate it."
        )
        return
        
    chunks = []
    logging.info(f"Loading data from {jsonl_file}")
    with open(jsonl_file, encoding="utf-8") as f:
        for l in f:
            if l.strip():
                chunks.append(json.loads(l))
                    
    logging.info(f"Loaded total {len(chunks)} chunks.")
    
    setup_meilisearch(chunks)
    logging.info("Ingestion complete.")

if __name__ == "__main__":
    main()
