"""
Stage 3: Translate Hindi commentary -> English commentary, chunk-wise,
using google/translategemma-4b-it in TEXT mode (not image mode -- we already
have clean OCR'd, chunked Hindi text from Stage 2, so text translation gives
much more reliable shloka-wise alignment than re-extracting from page images).

Install:
    pip install transformers accelerate torch --break-system-packages
    huggingface-cli login   # required once -- TranslateGemma is gated, you must
                             # accept Google's Gemma license on your HF account first:
                             # https://huggingface.co/google/translategemma-4b-it

Usage (GPU):
    python 03_translate_gemma.py --in sharangadhara_hindi_chunks.jsonl \
        --out sharangadhara_translated.jsonl --device cuda

Usage (no GPU / CPU fallback -- slow, but works):
    python 03_translate_gemma.py --in sharangadhara_hindi_chunks.jsonl \
        --out sharangadhara_translated.jsonl --device cpu

Usage (quantized, lower VRAM -- needs bitsandbytes):
    pip install bitsandbytes --break-system-packages
    python 03_translate_gemma.py --in sharangadhara_hindi_chunks.jsonl \
        --out sharangadhara_translated.jsonl --device cuda --load-in-4bit

This script is resumable: it skips chunk_ids already present in --out, so if it
crashes or you stop it partway through 356 pages' worth of chunks, just re-run
the same command.
"""

import argparse
import json
import os

import torch
from transformers import pipeline


def load_translator(device: str, load_in_4bit: bool):
    kwargs = {}
    if load_in_4bit:
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
        kwargs["device_map"] = "auto"
    else:
        kwargs["device"] = device
        kwargs["dtype"] = torch.bfloat16 if device == "cuda" else torch.float32

    return pipeline("image-text-to-text", model="google/translategemma-4b-it", **kwargs)


def translate_lines(pipe, lines, source_lang="hi", target_lang="en-US", max_new_tokens=400):
    """Translate a list of Hindi lines. Joins them with newlines in one call
    per chunk (cheaper than one call per line) then splits back out."""
    if not lines:
        return []

    joined = "\n".join(lines)
    messages = [{
        "role": "user",
        "content": [{
            "type": "text",
            "source_lang_code": source_lang,
            "target_lang_code": target_lang,
            "text": joined,
        }],
    }]
    output = pipe(text=messages, max_new_tokens=max_new_tokens)
    translated = output[0]["generated_text"][-1]["content"]
    # Re-split on newlines; fall back to a single-item list if the model
    # collapsed line breaks during translation.
    out_lines = [ln.strip() for ln in translated.splitlines() if ln.strip()]
    return out_lines if out_lines else [translated.strip()]


def run(in_path, out_path, device, load_in_4bit, source_lang, target_lang):
    pipe = load_translator(device, load_in_4bit)

    done_ids = set()
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    done_ids.add(json.loads(line)["chunk_id"])
                except Exception:
                    pass

    with open(in_path, "r", encoding="utf-8") as in_f, \
         open(out_path, "a", encoding="utf-8") as out_f:
        for line in in_f:
            record = json.loads(line)
            if record["chunk_id"] in done_ids:
                continue

            # Translate both the shloka text and the Hindi commentary, if you
            # want an English gloss of the verse too. Comment out the
            # sanskrit_text line if you only need the commentary translated.
            try:
                record["english_verse_gloss"] = translate_lines(
                    pipe, record.get("sanskrit_text", []), source_lang, target_lang
                )
            except Exception as e:
                print(f"  [warn] verse translation failed for {record['chunk_id']}: {e}")
                record["english_verse_gloss"] = []

            try:
                record["english_commentary"] = translate_lines(
                    pipe, record.get("commentary", []), source_lang, target_lang
                )
            except Exception as e:
                print(f"  [warn] commentary translation failed for {record['chunk_id']}: {e}")
                record["english_commentary"] = []

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()
            print(f"  translated {record['chunk_id']}")

    print(f"Done. Wrote translations to {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input JSONL from Stage 2")
    ap.add_argument("--out", dest="out_path", required=True, help="Output JSONL with english fields added")
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    ap.add_argument("--load-in-4bit", action="store_true", help="Quantize to 4-bit (needs bitsandbytes)")
    ap.add_argument("--source-lang", default="hi")
    ap.add_argument("--target-lang", default="en-US")
    args = ap.parse_args()

    run(args.in_path, args.out_path, args.device, args.load_in_4bit, args.source_lang, args.target_lang)
