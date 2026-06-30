"""
STEP 5: RE-RANKING + AYURPARAM COMPARISON
Takes top-20 MeiliSearch hits and re-ranks using Gemini API.
Also supports comparing your corpus vs AyurParam.

Usage:
    python 5_reranker.py "jwara treatment with herbs"

Install:
    pip install google-generativeai

Set env:
    export GOOGLE_API_KEY="your-gemini-key"
"""

import json
import os
import argparse
import sys

# Lazy import so module works even if google-generativeai not installed
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from anthropic import Anthropic

# ─────────────────────────── Prompts ────────────────────────────

RERANK_PROMPT = """You are a senior Ayurveda scholar and physician.

A user searched for: "{query}"

Below are {n} candidate shlokas retrieved from classical Ayurvedic texts.
Score each one 0-10 for relevance to the query.

Scoring criteria:
- 9-10: Directly answers the query with clinical specifics
- 7-8: Highly relevant, mentions key concepts
- 5-6: Partially relevant, related topic
- 3-4: Tangentially related
- 0-2: Not relevant

Candidates:
{candidates}

Return ONLY a JSON array (no markdown, no explanation):
[
  {{"chunk_id": "...", "score": 8, "reason": "one line why"}},
  ...
]
"""

COMPARE_PROMPT = """You are an Ayurveda scholar comparing two sources on the same topic.

Topic / Query: "{topic}"

Source A (Our corpus):
{our_text}

Source B (AyurParam / Reference):
{ref_text}

Analyze and return ONLY this JSON (no markdown):
{{
  "agreements": ["point 1", "point 2"],
  "contradictions": ["point 1"],
  "unique_to_ours": ["what only our corpus says"],
  "unique_to_reference": ["what only reference says"],
  "more_specific": "ours OR reference",
  "clinical_note": "one sentence clinical takeaway"
}}
"""

SUMMARY_PROMPT = """You are an Ayurveda clinical summarizer.

A physician searched for: "{query}"
These shlokas were retrieved:

{shlokas}

Write a clinical summary (max 200 words) covering:
1. Main principle / therapeutic approach
2. Key dravyas (herbs/substances) mentioned
3. Dosha perspective
4. Cross-text variations or contradictions (if any)
5. Clinical recommendation

Be precise. Use Ayurvedic terminology.
"""


# ─────────────────────────── Re-ranker ────────────────────────────

def rerank_with_gemini(query: str, hits: list[dict]) -> list[dict]:
    """Re-rank hits using Gemini."""
    if not GEMINI_AVAILABLE:
        print("[warn] google-generativeai not installed. pip install google-generativeai")
        return hits

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[warn] GOOGLE_API_KEY not set. Skipping re-rank.")
        return hits

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    candidates = []
    for h in hits[:20]:
        candidates.append({
            "chunk_id": h["chunk_id"],
            "topic": h.get("topic_heading", ""),
            "sthana": h.get("sthana", ""),
            "commentary": h.get("commentary", "")[:400],
            "transliteration": h.get("transliteration", "")[:200]
        })

    prompt = RERANK_PROMPT.format(
        query=query,
        n=len(candidates),
        candidates=json.dumps(candidates, ensure_ascii=False, indent=2)
    )

    try:
        resp = model.generate_content(prompt)
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scores = json.loads(raw.strip())
    except Exception as e:
        print(f"[warn] Gemini re-rank failed: {e}")
        return hits

    score_map = {s["chunk_id"]: s["score"] for s in scores}
    reason_map = {s["chunk_id"]: s.get("reason", "") for s in scores}

    for h in hits:
        h["rerank_score"] = score_map.get(h["chunk_id"], 0)
        h["rerank_reason"] = reason_map.get(h["chunk_id"], "")

    return sorted(hits, key=lambda x: x["rerank_score"], reverse=True)


def rerank_with_claude(query: str, hits: list[dict]) -> list[dict]:
    """Fallback re-ranker using Claude (if Gemini not available)."""
    client = Anthropic()

    candidates = []
    for h in hits[:20]:
        candidates.append({
            "chunk_id": h["chunk_id"],
            "topic": h.get("topic_heading", ""),
            "commentary": h.get("commentary", "")[:400]
        })

    prompt = RERANK_PROMPT.format(
        query=query,
        n=len(candidates),
        candidates=json.dumps(candidates, ensure_ascii=False, indent=2)
    )

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scores = json.loads(raw.strip())
    except Exception as e:
        print(f"[warn] Claude re-rank failed: {e}")
        return hits

    score_map = {s["chunk_id"]: s["score"] for s in scores}
    for h in hits:
        h["rerank_score"] = score_map.get(h["chunk_id"], 0)

    return sorted(hits, key=lambda x: x["rerank_score"], reverse=True)


# ─────────────────────────── AyurParam compare ────────────────────────────

def compare_with_ayurparam(topic: str, our_text: str, ayurparam_text: str) -> dict:
    """Compare your corpus shloka vs AyurParam reference."""
    client = Anthropic()
    prompt = COMPARE_PROMPT.format(
        topic=topic,
        our_text=our_text[:1000],
        ref_text=ayurparam_text[:1000]
    )
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ─────────────────────────── Transcript summary ────────────────────────────

def summarize_session(query: str, hits: list[dict]) -> str:
    """Generate clinical summary of retrieved shlokas."""
    client = Anthropic()

    shlokas = []
    for h in hits[:8]:
        entry = f"[{h['chunk_id']}] {h.get('topic_heading','')}\n{h.get('commentary','')[:300]}"
        shlokas.append(entry)

    prompt = SUMMARY_PROMPT.format(
        query=query,
        shlokas="\n\n---\n\n".join(shlokas)
    )

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text.strip()


# ─────────────────────────── CLI ────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="jwara vata treatment")
    parser.add_argument("--use-gemini", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args()

    # Import search
    sys.path.insert(0, ".")
    from _4_hybrid_search import search
    hits = search(args.query, alpha=0.5, top_k=20)

    print(f"Retrieved {len(hits)} hits. Re-ranking...")

    if args.use_gemini:
        ranked = rerank_with_gemini(args.query, hits)
    else:
        ranked = rerank_with_claude(args.query, hits)

    print(f"\n=== Top 5 after re-ranking ===")
    for i, h in enumerate(ranked[:5], 1):
        score = h.get("rerank_score", "?")
        reason = h.get("rerank_reason", "")
        print(f"{i}. [{score}/10] {h.get('chunk_id')} — {h.get('topic_heading','')}")
        if reason:
            print(f"   Reason: {reason}")

    if args.summarize:
        print(f"\n=== Clinical Summary ===")
        summary = summarize_session(args.query, ranked[:8])
        print(summary)
