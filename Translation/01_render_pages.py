"""
Stage 1: Render each PDF page to a PNG image for OCR.

Install:
    pip install pdf2image --break-system-packages
    # System dependency (Ubuntu/Debian): sudo apt-get install poppler-utils

Usage:
    python 01_render_pages.py \
        --pdf "Sharangadhara_Samhita_-_Hindi_Commentry.pdf" \
        --out pages/ \
        --dpi 300
"""

import argparse
import os
from pdf2image import convert_from_path, pdfinfo_from_path


def render_pages(pdf_path: str, out_dir: str, dpi: int = 300, start_page: int = 1, end_page: int = None):
    os.makedirs(out_dir, exist_ok=True)

    info = pdfinfo_from_path(pdf_path)
    total_pages = info["Pages"]
    end_page = end_page or total_pages
    print(f"PDF has {total_pages} pages. Rendering {start_page}-{end_page} at {dpi} DPI.")

    # Render in batches to avoid loading all 356 pages into memory at once.
    batch_size = 20
    for batch_start in range(start_page, end_page + 1, batch_size):
        batch_end = min(batch_start + batch_size - 1, end_page)
        images = convert_from_path(
            pdf_path, dpi=dpi, first_page=batch_start, last_page=batch_end
        )
        for offset, img in enumerate(images):
            page_num = batch_start + offset
            out_path = os.path.join(out_dir, f"page_{page_num:04d}.png")
            if os.path.exists(out_path):
                continue
            img.save(out_path, "PNG")
            print(f"  saved {out_path}")

    print("Done rendering pages.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Path to the source PDF")
    ap.add_argument("--out", default="pages", help="Output directory for page images")
    ap.add_argument("--dpi", type=int, default=300, help="Render DPI (300 is a good OCR default)")
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--end-page", type=int, default=None)
    args = ap.parse_args()

    render_pages(args.pdf, args.out, args.dpi, args.start_page, args.end_page)
