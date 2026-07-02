import os
import glob
import json
import logging
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MODEL_NAME = "intfloat/multilingual-e5-small"

def main():
    logging.info(f"Loading embedding model: {MODEL_NAME}")
    try:
        model = SentenceTransformer(MODEL_NAME)
    except Exception as e:
        logging.error(f"Failed to load model: {e}")
        return

    jsonl_files = glob.glob("Final data/*.jsonl")
    if not jsonl_files:
        logging.error("No JSONL files found in Final data/")
        return

    all_chunks = []
    
    # We want to deduplicate by chunk_id just in case
    seen_ids = set()

    for fpath in jsonl_files:
        logging.info(f"Reading {fpath}")
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                c = json.loads(line)
                
                # Clean chunk_id matching ingest.py logic
                chunk_id = str(c.get('chunk_id', '')).replace('.','_').replace('/','_')
                c['chunk_id'] = chunk_id
                
                if chunk_id in seen_ids:
                    continue
                seen_ids.add(chunk_id)

                for field in ['dosha','roga','dravya','karma']:
                    if not isinstance(c.get(field), list):
                        c[field] = []
                
                all_chunks.append(c)
                
    logging.info(f"Total unique chunks loaded: {len(all_chunks)}")
    
    # Generate embeddings
    logging.info("Generating embeddings (this may take a while)...")
    texts_to_embed = []
    for c in all_chunks:
        # Template from ingest.py: '{{doc.topic_heading}} {{doc.transliteration}} {{doc.commentary}}'
        th = c.get('topic_heading', '')
        tr = c.get('transliteration', '')
        co = c.get('commentary', '')
        text = f"{th} {tr} {co}".strip()
        texts_to_embed.append(text)
        
    embeddings = model.encode(texts_to_embed, show_progress_bar=True, batch_size=32)
    
    # Add _vectors field
    for i, c in enumerate(all_chunks):
        c['_vectors'] = {'default': embeddings[i].tolist()}
        
    output_path = "merged_books_with_embeddings.jsonl"
    logging.info(f"Writing output to {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            
    logging.info("Done.")

if __name__ == "__main__":
    main()
