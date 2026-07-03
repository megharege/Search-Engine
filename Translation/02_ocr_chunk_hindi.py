"""
Stage 2: OCR each page image (Devanagari/Hindi) and chunk shloka-wise into JSONL,
mirroring the schema used in your other pipelines (chunk_id, sthana, verse_id,
sanskrit_text, commentary).

Install:
    pip install pytesseract pillow --break-system-packages
    # System dependencies (Ubuntu/Debian):
    #   sudo apt-get install tesseract-ocr tesseract-ocr-hin

Usage:
    python 02_ocr_chunk_hindi.py --pages pages/ --out sharangadhara_hindi_chunks.jsonl \
        --khanda "Purvakhanda" --start-page 1 --end-page 356

NOTES ON CHUNKING LOGIC (tune this to your book's layout):
- This script treats each page's OCR text as a stream of lines.
- A new verse/shloka boundary is detected by a Devanagari verse-end marker,
  e.g. "॥ १ ॥", "॥१॥", "।।1।।", or plain "॥ 1 ॥" (mixed Devanagari/Arabic numerals
  are both handled).
- Lines BEFORE the marker on that boundary are treated as `sanskrit_text`
  (the shloka itself); lines AFTER, up to the next marker, are treated as
  `commentary` (the Hindi vyakhya/tika).
- If your book's commentary sections start with a recognizable heading word
  (e.g. "टीका", "व्याख्या", "भावार्थ"), add it to COMMENTARY_HEADERS below to
  improve the split between verse and commentary within a block.
- This is a best-effort heuristic chunker for scanned OCR text, which is noisy.
  Expect to hand-correct some boundaries -- OCR quality on Devanagari commentary
  fonts varies a lot page to page. Consider spot-checking ~10 random chunks
  after running before moving to translation (Stage 3).
"""

import argparse
import glob
import json
import os
import re

import pytesseract
from PIL import Image

# Devanagari verse-end marker: double danda, optionally with a verse number
# (Devanagari or Arabic digits) between single dandas or spaces.
VERSE_MARKER_RE = re.compile(r"॥\s*[०-९0-9]*\s*॥|।।\s*[०-९0-9]*\s*।।")

COMMENTARY_HEADERS = ["टीका", "व्याख्या", "भावार्थ", "टिप्पणी"]


def ocr_page(image_path: str) -> str:
    img = Image.open(image_path)
    # lang='hin' requires tesseract-ocr-hin installed.
    text = pytesseract.image_to_string(img, lang="hin")
    return text


def split_into_blocks(page_text: str):
    """Split raw OCR text into (sanskrit_text, commentary) blocks at verse markers."""
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    blocks = []
    current_verse_lines = []
    current_commentary_lines = []
    in_commentary = False

    for line in lines:
        if any(h in line for h in COMMENTARY_HEADERS):
            in_commentary = True
            continue

        if VERSE_MARKER_RE.search(line):
            # This line closes out a verse. Split what precedes the marker
            # off as the tail of the sanskrit_text, and start commentary mode
            # for subsequent lines until the next verse marker.
            pre, _, _post = VERSE_MARKER_RE.partition(line)
            if pre.strip():
                current_verse_lines.append(pre.strip())
            blocks.append({
                "sanskrit_text": current_verse_lines,
                "commentary": current_commentary_lines,
            })
            current_verse_lines = []
            current_commentary_lines = []
            in_commentary = False
            continue

        if in_commentary:
            current_commentary_lines.append(line)
        else:
            current_verse_lines.append(line)

    # Trailing partial block (e.g., commentary continues onto next page)
    if current_verse_lines or current_commentary_lines:
        blocks.append({
            "sanskrit_text": current_verse_lines,
            "commentary": current_commentary_lines,
            "incomplete": True,  # flag so Stage 3 / manual review knows this may
                                  # need merging with the next page's opening block
        })

    return blocks


def run(pages_dir, out_path, khanda, start_page, end_page):
    page_files = sorted(glob.glob(os.path.join(pages_dir, "page_*.png")))
    if start_page or end_page:
        def in_range(fp):
            n = int(re.search(r"page_(\d+)", fp).group(1))
            if start_page and n < start_page:
                return False
            if end_page and n > end_page:
                return False
            return True
        page_files = [fp for fp in page_files if in_range(fp)]

    # Resume support: read chunk_ids already written.
    done_ids = set()
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    done_ids.add(json.loads(line)["chunk_id"])
                except Exception:
                    pass

    verse_counter = 1
    pending_verse_lines, pending_commentary_lines = [], []

    with open(out_path, "a", encoding="utf-8") as out_f:
        for page_path in page_files:
            page_num = int(re.search(r"page_(\d+)", page_path).group(1))
            print(f"OCR page {page_num} ...")
            text = ocr_page(page_path)
            blocks = split_into_blocks(text)

            for block in blocks:
                # Merge any pending partial block from the previous page.
                sanskrit_lines = pending_verse_lines + block["sanskrit_text"]
                commentary_lines = pending_commentary_lines + block["commentary"]
                pending_verse_lines, pending_commentary_lines = [], []

                if block.get("incomplete"):
                    # Hold this block over to merge with the next page's start.
                    pending_verse_lines = sanskrit_lines
                    pending_commentary_lines = commentary_lines
                    continue

                if not sanskrit_lines and not commentary_lines:
                    continue

                chunk_id = f"{khanda.lower()}_{verse_counter:04d}"
                if chunk_id in done_ids:
                    verse_counter += 1
                    continue

                record = {
                    "chunk_id": chunk_id,
                    "book": "Sharangadhara Samhita",
                    "khanda": khanda,
                    "page_number": page_num,
                    "verse_id": verse_counter,
                    "sanskrit_text": sanskrit_lines,
                    "commentary": commentary_lines,       # Hindi commentary
                    "english_commentary": [],              # filled in Stage 3
                    "categories_found_en": [],              # filled in Stage 4
                    "primary_category_en": None,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_f.flush()
                verse_counter += 1

    print(f"Done. Wrote chunks to {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", required=True, help="Directory of page_*.png images from Stage 1")
    ap.add_argument("--out", required=True, help="Output JSONL path")
    ap.add_argument("--khanda", default="khanda", help="Section name prefix for chunk_id, e.g. Purvakhanda")
    ap.add_argument("--start-page", type=int, default=None)
    ap.add_argument("--end-page", type=int, default=None)
    args = ap.parse_args()

    run(args.pages, args.out, args.khanda, args.start_page, args.end_page)
