"""
STEP 1: TAG EXTRACTION
Reads corpus.jsonl, adds Ayurvedic tags to each chunk, writes corpus_tagged.jsonl

Usage:
    python 1_tag_extractor.py --input corpus.jsonl --output corpus_tagged.jsonl

Install:
    pip install anthropic
"""

import json
import argparse
import time
from anthropic import Anthropic

client = Anthropic()  # reads ANTHROPIC_API_KEY from env

TAGGING_PROMPT = """You are an Ayurveda expert. Analyze this Ayurvedic text chunk and return ONLY a JSON object.

Chunk topic: {topic}
Transliteration: {transliteration}
Commentary: {commentary}

Return ONLY this JSON (no explanation, no markdown):
{{
  "dosha": [],
  "roga": [],
  "dravya": [],
  "karma": [],
  "content_type": ""
}}

Rules:
- dosha: list from [vata, pitta, kapha, tridosha, vata-pitta, vata-kapha, pitta-kapha] — only if clearly mentioned
- roga: diseases discussed (e.g. jwara, prameha, kasa, arsha, shotha, raktapitta)
- dravya: herbs or substances named (e.g. haritaki, shunthi, guduchi, ashwagandha)
- karma: therapeutic actions (e.g. deepana, pachana, shodhana, rasayana, vamana, virechana)
- content_type: one of [verse, commentary, definition, procedure, classification, description]
- Use empty lists [] if nothing found — never guess
"""


def tag_chunk(chunk: dict) -> dict:
    topic = chunk.get("topic_heading", "")
    trans = chunk.get("transliteration", "")[:600]
    comm = chunk.get("commentary", "")[:800]

    # Skip if no meaningful text
    if not (trans or comm):
        return {"dosha": [], "roga": [], "dravya": [], "karma": [], "content_type": "verse"}

    prompt = TAGGING_PROMPT.format(topic=topic, transliteration=trans, commentary=comm)

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"  [warn] Tagging failed for {chunk.get('chunk_id','?')}: {e}")
        return {"dosha": [], "roga": [], "dravya": [], "karma": [], "content_type": "verse"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="corpus.jsonl")
    parser.add_argument("--output", default="corpus_tagged.jsonl")
    parser.add_argument("--limit", type=int, default=None, help="Process only N chunks (for testing)")
    parser.add_argument("--delay", type=float, default=0.3, help="Seconds between API calls")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]

    if args.limit:
        chunks = chunks[:args.limit]

    print(f"Tagging {len(chunks)} chunks...")

    tagged = []
    for i, chunk in enumerate(chunks):
        tags = tag_chunk(chunk)
        chunk.update(tags)
        tagged.append(chunk)

        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(chunks)} done")

        time.sleep(args.delay)  # rate limit buffer

    with open(args.output, "w", encoding="utf-8") as f:
        for c in tagged:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\nDone. Written to {args.output}")
    # Print tag coverage stats
    has_dosha = sum(1 for c in tagged if c.get("dosha"))
    has_roga = sum(1 for c in tagged if c.get("roga"))
    has_dravya = sum(1 for c in tagged if c.get("dravya"))
    print(f"Tag coverage — dosha: {has_dosha}, roga: {has_roga}, dravya: {has_dravya}")


if __name__ == "__main__":
    main()
