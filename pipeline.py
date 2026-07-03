"""
Run the full pipeline in order:

  Step 1 — combine   : merge 4 raw JSONL files → data/combined.jsonl
  Step 2 — embed     : generate embeddings     → data/embeddings.npz
  Step 3 — ingest    : load into Meilisearch

Usage:
    python pipeline.py                # all 3 steps
    python pipeline.py --steps 1 2   # only combine + embed (no Meili needed)
    python pipeline.py --steps 3     # only ingest (re-use cached embeddings)
    python pipeline.py --force-embed # recompute embeddings even if cache is valid
"""
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", nargs="+", type=int, choices=[1, 2, 3],
                        default=[1, 2, 3], help="Which steps to run (default: all)")
    parser.add_argument("--force-embed", action="store_true",
                        help="Recompute embeddings even if combined.jsonl hasn't changed")
    args = parser.parse_args()

    if 1 in args.steps:
        print("\n── Step 1: Combine ──────────────────────────────")
        from src.combine import combine
        combine()

    if 2 in args.steps:
        print("\n── Step 2: Embed ────────────────────────────────")
        from src.embed import generate
        generate(force=args.force_embed)

    if 3 in args.steps:
        print("\n── Step 3: Ingest into Meilisearch ─────────────")
        from src.ingest_meili import ingest
        ingest()

    print("\n✓ Pipeline complete.")

if __name__ == "__main__":
    main()
