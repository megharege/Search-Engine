import json
from transformers import AutoTokenizer
from collections import defaultdict
import re
import os

print("Loading tokenizer...")
try:
    # unsloth/gemma-7b has the exact same SentencePiece tokenizer (256k vocab) as all gemma models
    # and is not gated, allowing it to be downloaded without HF login.
    tokenizer = AutoTokenizer.from_pretrained("unsloth/gemma-7b")
    print("Loaded tokenizer successfully.")
except Exception as e:
    print(f"Failed to load tokenizer: {e}")
    exit(1)

data_file = 'Final data_backup/combined.jsonl'
books = defaultdict(lambda: {
    'Sanskrit': {'total': 0, 'min': float('inf'), 'max': 0, 'chunks': 0},
    'Transliteration': {'total': 0, 'min': float('inf'), 'max': 0, 'chunks': 0},
    'Commentary': {'total': 0, 'min': float('inf'), 'max': 0, 'chunks': 0},
    'English words': {'total': 0, 'min': float('inf'), 'max': 0, 'chunks': 0}
})

print(f"Reading {data_file}...")
with open(data_file, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            record = json.loads(line)
        except Exception:
            continue
            
        book = record.get('book_name') or record.get('source_file') or record.get('book_id', 'Unknown')
        
        # Helper to process field
        def process_field(text, field_name, is_english=False):
            if not text:
                return
            if is_english:
                # simple word count
                tokens = len(re.findall(r'\b\w+\b', text))
            else:
                tokens = len(tokenizer.encode(text, add_special_tokens=False))
                
            books[book][field_name]['total'] += tokens
            books[book][field_name]['chunks'] += 1
            if tokens < books[book][field_name]['min']:
                books[book][field_name]['min'] = tokens
            if tokens > books[book][field_name]['max']:
                books[book][field_name]['max'] = tokens

        process_field(record.get('sanskrit_text', ''), 'Sanskrit')
        process_field(record.get('transliteration', ''), 'Transliteration')
        process_field(record.get('commentary', ''), 'Commentary')
        process_field(record.get('commentary', ''), 'English words', is_english=True)

print("\nMarkdown Table:\n")
print("| Book | Field | Total Tokens | Avg Tokens | Min | Max |")
print("|------|-------|--------------|------------|-----|-----|")
for book in sorted(books.keys()):
    print(f"| **{book}** | Sanskrit | {books[book]['Sanskrit']['total']:,} | {books[book]['Sanskrit']['total'] / max(1, books[book]['Sanskrit']['chunks']):.1f} | {books[book]['Sanskrit']['min'] if books[book]['Sanskrit']['min'] != float('inf') else 0} | {books[book]['Sanskrit']['max']:,} |")
    print(f"| | Transliteration | {books[book]['Transliteration']['total']:,} | {books[book]['Transliteration']['total'] / max(1, books[book]['Transliteration']['chunks']):.1f} | {books[book]['Transliteration']['min'] if books[book]['Transliteration']['min'] != float('inf') else 0} | {books[book]['Transliteration']['max']:,} |")
    print(f"| | Commentary | {books[book]['Commentary']['total']:,} | {books[book]['Commentary']['total'] / max(1, books[book]['Commentary']['chunks']):.1f} | {books[book]['Commentary']['min'] if books[book]['Commentary']['min'] != float('inf') else 0} | {books[book]['Commentary']['max']:,} |")
    print(f"| | English words | {books[book]['English words']['total']:,} | {books[book]['English words']['total'] / max(1, books[book]['English words']['chunks']):.1f} | {books[book]['English words']['min'] if books[book]['English words']['min'] != float('inf') else 0} | {books[book]['English words']['max']:,} |")

