"""
STEP 6: FULL PIPELINE RUNNER
Runs the complete end-to-end pipeline from tagged JSONL to search results.
Also works as Antigravity (Jupyter) notebook — copy each CELL into a cell.

Usage:
    python 6_pipeline_runner.py --input corpus_tagged.jsonl --query "vata jwara"
"""

# ═══════════════════════════════════════════════
# CELL 1 — Install all dependencies
# ═══════════════════════════════════════════════
CELL_1 = """
!pip install meilisearch anthropic google-generativeai sentence-transformers

# Download and start MeiliSearch
import subprocess, os

if not os.path.exists('./meilisearch'):
    subprocess.run(['curl', '-L', 'https://install.meilisearch.com'], capture_output=False)

# Start MeiliSearch in background
proc = subprocess.Popen(
    ['./meilisearch', '--master-key=ayurveda-dev-key', '--no-analytics'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)
print("MeiliSearch started, PID:", proc.pid)

import time; time.sleep(3)  # wait for server
import meilisearch
client = meilisearch.Client('http://localhost:7700', 'ayurveda-dev-key')
print("Health:", client.health())
"""

# ═══════════════════════════════════════════════
# CELL 2 — Tag all chunks
# ═══════════════════════════════════════════════
CELL_2 = """
import json, time
from anthropic import Anthropic

client = Anthropic()  # set ANTHROPIC_API_KEY in env

TAGGING_PROMPT = '''You are an Ayurveda expert. Analyze this text and return ONLY JSON:
{{
  "dosha": [],
  "roga": [],
  "dravya": [],
  "karma": [],
  "content_type": ""
}}
Topic: {topic}
Commentary: {commentary}
Return only valid JSON.'''

def tag_chunk(chunk):
    prompt = TAGGING_PROMPT.format(
        topic=chunk.get('topic_heading',''),
        commentary=chunk.get('commentary','')[:600]
    )
    try:
        resp = client.messages.create(
            model='claude-sonnet-4-6', max_tokens=300,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return json.loads(resp.content[0].text.strip())
    except:
        return {"dosha":[],"roga":[],"dravya":[],"karma":[],"content_type":"verse"}

with open('corpus.jsonl') as f:
    chunks = [json.loads(l) for l in f if l.strip()]

print(f"Tagging {len(chunks)} chunks...")
for i, chunk in enumerate(chunks):
    tags = tag_chunk(chunk)
    chunk.update(tags)
    if (i+1) % 50 == 0: print(f"  {i+1}/{len(chunks)}")
    time.sleep(0.3)

with open('corpus_tagged.jsonl','w') as f:
    for c in chunks: f.write(json.dumps(c, ensure_ascii=False)+'\\n')
print("Done. Written corpus_tagged.jsonl")
"""

# ═══════════════════════════════════════════════
# CELL 3 — Setup MeiliSearch index
# ═══════════════════════════════════════════════
CELL_3 = """
import meilisearch, time

ms = meilisearch.Client('http://localhost:7700', 'ayurveda-dev-key')

def wait(task_uid):
    for _ in range(60):
        t = ms.get_task(task_uid)
        if t.status in ('succeeded','failed'): return t
        time.sleep(1)

# Create index
try:
    idx = ms.get_index('ayurveda')
    print("Index exists")
except:
    t = ms.create_index('ayurveda', {'primaryKey': 'chunk_id'})
    wait(t.task_uid)
    idx = ms.get_index('ayurveda')
    print("Index created")

wait(idx.update_searchable_attributes([
    'topic_heading','transliteration','commentary',
    'chapter_title','sanskrit_text','sthana','roga','dravya'
]).task_uid)

wait(idx.update_filterable_attributes([
    'sthana','chapter_number','primary_category',
    'dosha','roga','dravya','karma','content_type','source_file'
]).task_uid)

wait(idx.update_embedders({
    'default': {
        'source': 'huggingFace',
        'model': 'intfloat/multilingual-e5-small',
        'documentTemplate': '{{doc.topic_heading}} {{doc.transliteration}} {{doc.commentary}}'
    }
}).task_uid)

print("Index setup complete")
"""

# ═══════════════════════════════════════════════
# CELL 4 — Upload documents
# ═══════════════════════════════════════════════
CELL_4 = """
import meilisearch, json, time

ms = meilisearch.Client('http://localhost:7700', 'ayurveda-dev-key')
idx = ms.index('ayurveda')

def wait(task_uid):
    for _ in range(120):
        t = ms.get_task(task_uid)
        if t.status == 'succeeded': return t
        if t.status == 'failed': raise RuntimeError(t.error)
        time.sleep(1)

with open('corpus_tagged.jsonl') as f:
    chunks = [json.loads(l) for l in f if l.strip()]

# Clean chunk_ids (no dots allowed)
for c in chunks:
    c['chunk_id'] = str(c['chunk_id']).replace('.','_').replace('/','_')
    for field in ['dosha','roga','dravya','karma']:
        if not isinstance(c.get(field), list): c[field] = []

print(f"Uploading {len(chunks)} chunks...")
BATCH = 500
for i in range(0, len(chunks), BATCH):
    batch = chunks[i:i+BATCH]
    wait(idx.add_documents(batch, primary_key='chunk_id').task_uid)
    print(f"  {min(i+BATCH, len(chunks))}/{len(chunks)}")

print("Indexed:", idx.get_stats().number_of_documents, "docs")
"""

# ═══════════════════════════════════════════════
# CELL 5 — Test hybrid search
# ═══════════════════════════════════════════════
CELL_5 = """
import meilisearch

ms = meilisearch.Client('http://localhost:7700', 'ayurveda-dev-key')
idx = ms.index('ayurveda')

def search(query, alpha=0.5, dosha=None, book=None, top_k=10):
    filters = []
    if dosha: filters.append(f'dosha = "{dosha}"')
    if book:  filters.append(f'source_file = "{book}"')
    params = {
        'limit': top_k,
        'attributesToHighlight': ['commentary','transliteration'],
    }
    if alpha > 0:
        params['hybrid'] = {'semanticRatio': alpha, 'embedder': 'default'}
    if filters:
        params['filter'] = ' AND '.join(filters)
    return idx.search(query, params)['hits']

# Test queries
for query in [
    'vata dosha treatment fever',
    'haritaki herb uses',
    'eight branches of ayurveda'
]:
    hits = search(query)
    print(f"Query: '{query}' → {len(hits)} hits")
    for h in hits[:3]:
        print(f"  [{h['chunk_id']}] {h.get('topic_heading','')}")
    print()
"""

# ═══════════════════════════════════════════════
# CELL 6 — Re-rank and summarize
# ═══════════════════════════════════════════════
CELL_6 = """
import json
from anthropic import Anthropic

client = Anthropic()

RERANK_PROMPT = '''You are a senior Ayurveda scholar.
Query: "{query}"
Score each candidate 0-10 for relevance. Return ONLY JSON array:
[{{"chunk_id":"...","score":8,"reason":"..."}}]

Candidates:
{candidates}'''

SUMMARY_PROMPT = '''Summarize these Ayurvedic shlokas for query: "{query}"
Write 150 words covering: main principle, key herbs, dosha perspective, contradictions.
Shlokas: {shlokas}'''

def rerank(query, hits):
    cands = [{"chunk_id":h["chunk_id"],"topic":h.get("topic_heading",""),
              "text":h.get("commentary","")[:300]} for h in hits[:20]]
    resp = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=600,
        messages=[{'role':'user','content': RERANK_PROMPT.format(
            query=query, candidates=json.dumps(cands))}]
    )
    raw = resp.content[0].text.strip().lstrip('```json').rstrip('```')
    scores = json.loads(raw)
    sm = {s['chunk_id']: s['score'] for s in scores}
    for h in hits: h['score'] = sm.get(h['chunk_id'], 0)
    return sorted(hits, key=lambda x: x['score'], reverse=True)

def summarize(query, hits):
    texts = ["\\n".join([h.get('topic_heading',''), h.get('commentary','')[:250]]) for h in hits[:6]]
    resp = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=400,
        messages=[{'role':'user','content': SUMMARY_PROMPT.format(
            query=query, shlokas="\\n---\\n".join(texts))}]
    )
    return resp.content[0].text.strip()

# Run
query = "jwara treatment vata pitta"
hits = search(query, alpha=0.5, top_k=20)  # from Cell 5
ranked = rerank(query, hits)

print("Top 5 after re-ranking:")
for h in ranked[:5]:
    print(f"  [{h['score']}/10] {h['chunk_id']} — {h.get('topic_heading','')}")

print("\\n--- Clinical Summary ---")
print(summarize(query, ranked[:6]))
"""


# ═══════════════════════════════════════════════
# Actual runnable script (not notebook)
# ═══════════════════════════════════════════════
import argparse
import json
import sys
import time

def main():
    parser = argparse.ArgumentParser(description="Full Ayurveda RAG Pipeline")
    parser.add_argument("--input", default="corpus_tagged.jsonl", help="Tagged JSONL file")
    parser.add_argument("--query", default="vata dosha jwara treatment")
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--print-cells", action="store_true", help="Print notebook cells")
    args = parser.parse_args()

    if args.print_cells:
        cells = [CELL_1, CELL_2, CELL_3, CELL_4, CELL_5, CELL_6]
        for i, cell in enumerate(cells, 1):
            print(f"\n{'='*60}")
            print(f"CELL {i}")
            print('='*60)
            print(cell)
        return

    # Run search + rerank inline
    try:
        import meilisearch
    except ImportError:
        print("pip install meilisearch")
        sys.exit(1)

    from _4_hybrid_search import search
    from _5_reranker import rerank_with_claude, summarize_session

    print(f"Searching: '{args.query}' (alpha={args.alpha})")
    hits = search(args.query, alpha=args.alpha, top_k=20)
    print(f"Retrieved {len(hits)} hits. Re-ranking...")

    ranked = rerank_with_claude(args.query, hits)
    print(f"\nTop 5 results:")
    for i, h in enumerate(ranked[:5], 1):
        print(f"  {i}. [{h.get('rerank_score','?')}/10] {h['chunk_id']} — {h.get('topic_heading','')}")

    if args.summarize:
        print(f"\nClinical Summary:")
        print(summarize_session(args.query, ranked[:6]))


if __name__ == "__main__":
    main()
