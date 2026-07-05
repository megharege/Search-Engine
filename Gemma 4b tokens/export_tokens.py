import json
from transformers import AutoTokenizer
import os

print("Loading tokenizer...")
try:
    tokenizer = AutoTokenizer.from_pretrained("unsloth/gemma-7b")
    print("Loaded tokenizer successfully.")
except Exception as e:
    print(f"Failed to load tokenizer: {e}")
    exit(1)

data_file = 'Final data_backup/combined.jsonl'
output_file = 'gemma_4b_tokens_export.jsonl'

print(f"Reading {data_file} and writing to {output_file}...")
with open(data_file, 'r', encoding='utf-8') as f, open(output_file, 'w', encoding='utf-8') as out_f:
    for i, line in enumerate(f):
        try:
            record = json.loads(line)
        except Exception:
            continue
            
        chunk_id = record.get('chunk_id')
        if not chunk_id:
            continue
            
        def get_tokens(text):
            if not text:
                return []
            ids = tokenizer.encode(text, add_special_tokens=False)
            tokens = tokenizer.convert_ids_to_tokens(ids)
            # Clean up the byte representation if needed, but standard string is fine
            return tokens

        sanskrit_tokens = get_tokens(record.get('sanskrit_text', ''))
        translit_tokens = get_tokens(record.get('transliteration', ''))
        commentary_tokens = get_tokens(record.get('commentary', ''))
        
        out_record = {
            'chunk_id': chunk_id,
            'book_name': record.get('book_name') or record.get('source_file') or record.get('book_id', 'Unknown'),
            'sanskrit_tokens': sanskrit_tokens,
            'transliteration_tokens': translit_tokens,
            'commentary_tokens': commentary_tokens,
            'sanskrit_token_count': len(sanskrit_tokens),
            'transliteration_token_count': len(translit_tokens),
            'commentary_token_count': len(commentary_tokens)
        }
        
        out_f.write(json.dumps(out_record, ensure_ascii=False) + '\n')
        
        if (i + 1) % 500 == 0:
            print(f"Processed {i + 1} chunks...")

print(f"Done! Exported to {output_file}")
