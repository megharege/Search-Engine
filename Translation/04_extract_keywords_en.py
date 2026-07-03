"""
Stage 4: Fill categories_found_en / primary_category_en on each chunk by
keyword-matching against the English commentary + verse gloss produced in
Stage 3. Same pattern as your chunk_bp01.py taxonomy tagging, just run against
English text instead of Sanskrit/transliteration -- fills in ONLY these two
fields, leaves everything else untouched (per your zero-context-loss rule).

Usage:
    python 04_extract_keywords_en.py --in sharangadhara_translated.jsonl \
        --out sharangadhara_final.jsonl --taxonomy taxonomy_en.json

TAXONOMY FILE FORMAT (taxonomy_en.json) -- edit/extend to match your existing
category schema across the other texts (dosha/roga/dravya/karma etc.):
{
  "digestion": ["digestion", "digestive fire", "agni", "appetite"],
  "fever": ["fever", "pyrexia", "jwara"],
  "purification": ["purification", "shodhana", "cleansing", "detoxification"],
  ...
}
"""

import argparse
import json
import re


DEFAULT_TAXONOMY = {
    "dosha": ["vata", "pitta", "kapha", "dosha", "humor"],
    "digestion": ["digestion", "digestive fire", "agni", "appetite", "indigestion"],
    "fever": ["fever", "pyrexia"],
    "purification": ["purification", "shodhana", "cleansing", "detoxification", "emesis", "purgation"],
    "formulation": ["decoction", "kwatha", "churna", "powder", "paste", "oil", "ghee", "tablet", "pill"],
    "dravya": ["herb", "drug", "plant", "root", "leaf", "bark", "seed"],
    "measurement": ["weight", "measure", "tola", "pala", "seer", "ratti"],
    "anatomy": ["stomach", "intestine", "liver", "spleen", "heart", "blood", "bone"],
}


def load_taxonomy(path):
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_TAXONOMY


def find_categories(text: str, taxonomy: dict):
    text_lower = text.lower()
    found = []
    for category, keywords in taxonomy.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text_lower):
                found.append(category)
                break
    return found


def run(in_path, out_path, taxonomy_path):
    taxonomy = load_taxonomy(taxonomy_path)

    with open(in_path, "r", encoding="utf-8") as in_f, \
         open(out_path, "w", encoding="utf-8") as out_f:
        for line in in_f:
            record = json.loads(line)

            combined_text = " ".join(
                record.get("english_commentary", []) + record.get("english_verse_gloss", [])
            )
            categories = find_categories(combined_text, taxonomy)

            record["categories_found_en"] = categories
            record["primary_category_en"] = categories[0] if categories else None

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Done. Wrote {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument("--taxonomy", default=None, help="Optional custom taxonomy JSON file")
    args = ap.parse_args()

    run(args.in_path, args.out_path, args.taxonomy)
