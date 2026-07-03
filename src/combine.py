"""
Step 1: Combine all raw JSONL files into data/combined.jsonl

Each record gets two extra fields injected:
  book_id   - short identifier (MN1, MN2, SUS, AH)
  book_name - full readable name
  global_id - unique across all books: "{book_id}::{chunk_id}"

The one known data quirk is handled here:
  AH record AH_291 uses 'categories_fold' instead of 'categories_found' -- fixed.

Usage:
    python -m src.combine
"""
from __future__ import annotations
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR  = os.path.join(ROOT, "data", "raw")
OUT_PATH = os.path.join(ROOT, "data", "combined.jsonl")

BOOKS = [
    ("MN1", "Madhava Nidana - Part 1",  "B02-madhavanisana-pt1-final_output.jsonl"),
    ("MN2", "Madhava Nidana - Part 2",  "B03-madhavanisana-pt2-final_output.jsonl"),
    ("SUS", "Sushruta Samhita",          "sushrut-final_output.jsonl"),
    ("AH",  "Ashtanga Hridaya",          "ashtanga-hridaya-final_output.jsonl"),
]

def combine():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    total = 0
    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for book_id, book_name, fname in BOOKS:
            path = os.path.join(RAW_DIR, fname)
            n = 0
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)

                    # fix categories_fold typo (AH only, 1 record)
                    if "categories_fold" in rec:
                        rec.setdefault("categories_found", rec.pop("categories_fold"))
                    if not rec.get("categories_found"):
                        rec["categories_found"] = []

                    rec["book_id"]   = book_id
                    rec["book_name"] = book_name
                    rec["global_id"] = f"{book_id}::{rec['chunk_id']}"

                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
            print(f"  {book_id:4s}  {book_name:30s}  {n:4d} chunks")
            total += n
    print(f"  ─────────────────────────────────────────────────")
    print(f"  Total: {total} chunks  →  {OUT_PATH}")

if __name__ == "__main__":
    print("== Combining books ==")
    combine()
