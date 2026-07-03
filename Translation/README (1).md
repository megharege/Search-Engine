# Sharangadhara Samhita — Hindi Commentary → English Pipeline

Full run sequence, in order:

```bash
pip install pdf2image pytesseract pillow transformers accelerate torch --break-system-packages
# sudo apt-get install poppler-utils tesseract-ocr tesseract-ocr-hin

# 1. PDF pages -> images
python 01_render_pages.py --pdf "Sharangadhara_Samhita_-_Hindi_Commentry.pdf" --out pages/ --dpi 300

# 2. OCR (Devanagari) + shloka-wise chunking -> Hindi JSONL
python 02_ocr_chunk_hindi.py --pages pages/ --out sharangadhara_hindi_chunks.jsonl --khanda Purvakhanda

# 3. Translate Hindi -> English per chunk (TranslateGemma-4B-IT, text mode)
huggingface-cli login   # once, after accepting the Gemma license on HF
python 03_translate_gemma.py --in sharangadhara_hindi_chunks.jsonl --out sharangadhara_translated.jsonl --device cuda

# 4. Keyword/category extraction from English commentary
python 04_extract_keywords_en.py --in sharangadhara_translated.jsonl --out sharangadhara_final.jsonl
```

## Why text-mode translation, not image-mode

TranslateGemma-4B-IT can translate directly from a page image, but that
collapses shloka boundaries into running prose — you'd lose the verse-wise
alignment your other pipelines depend on. Doing OCR + chunking first (stage 2)
and then translating each chunk's Hindi lines as text (stage 3) keeps the
`chunk_id`/`verse_id` structure intact end-to-end, matching how
`chunk_json.py` and `chunk_bp01.py` already work for your other texts.

## Known rough edges to expect

- **OCR quality**: scanned Hindi commentary fonts are noisy for Tesseract.
  Spot-check ~10-20 chunks after Stage 2 before burning GPU hours on
  translation. If quality is poor, consider Tesseract's `--psm` page
  segmentation modes, or swapping in a VLM-based OCR pass instead
  (TranslateGemma itself, or Gemini/Claude vision) — happy to build that
  variant if Tesseract output looks bad on your scans.
- **Verse-marker regex** in Stage 2 (`VERSE_MARKER_RE`) assumes `॥ १ ॥` /
  `।।1।।` style boundaries. If Sharangadhara Samhita numbers differently,
  adjust the regex — send me a sample OCR'd page and I'll tune it.
- **Gated model**: you must accept the Gemma license on your Hugging Face
  account (logged in) before `huggingface-cli login` will let the script pull
  weights: https://huggingface.co/google/translategemma-4b-it
- **356 pages** on a 4B VLM will take a while even on GPU — Stage 3 is
  checkpointed per chunk_id, so it's safe to stop/resume anytime.
- **Field naming**: I used `english_commentary` and `english_verse_gloss` to
  parallel your existing `commentary`/`sanskrit_text` fields — rename in the
  scripts if your downstream MeiliSearch/Qdrant schema expects different keys.
