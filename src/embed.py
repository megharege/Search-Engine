"""
Step 2: Generate and save embeddings from data/combined.jsonl

Model : microsoft/harrier-oss-v1-0.6b  (MIT license, 1024-dim, fits 6GB VRAM)
Fields: transliteration + commentary   (per spec — never raw Sanskrit)

Output: data/embeddings.npz
  global_ids          : (N,)     string array  — matches combined.jsonl order
  transliteration_emb : (N,1024) float32
  commentary_emb      : (N,1024) float32

Caching: if embeddings.npz exists AND combined.jsonl hasn't changed (sha256),
the run is skipped automatically. Pass --force to recompute.

Usage:
    python -m src.embed
    python -m src.embed --force
"""
from __future__ import annotations
import argparse, hashlib, json, os
import numpy as np

ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMBINED   = os.path.join(ROOT, "data", "combined.jsonl")
EMB_PATH   = os.path.join(ROOT, "data", "embeddings.npz")
HASH_PATH  = EMB_PATH + ".sha256"
MODEL_NAME = "microsoft/harrier-oss-v1-0.6b"
EMBED_DIM  = 1024

# Instruction prefix for query-side encoding (model card requirement)
QUERY_INSTRUCTION = (
    "Given a clinical search query describing a symptom, disease, or Ayurvedic "
    "treatment, retrieve the relevant verse commentary"
)

# ── singleton model wrapper ───────────────────────────────────────────────────
class HarrierEmbedder:
    _model = None

    def load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"  Loading {MODEL_NAME} on {device} ...")
            self._model = SentenceTransformer(
                MODEL_NAME,
                model_kwargs={"dtype": "auto"},
                device=device,
            )
        return self._model

    def encode_passages(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        return self.load().encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")

    def encode_query(self, text: str) -> np.ndarray:
        prompt = f"Instruct: {QUERY_INSTRUCTION}\nQuery: "
        return self.load().encode(
            [text],
            prompt=prompt,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0].astype("float32")


embedder = HarrierEmbedder()


# ── helpers ───────────────────────────────────────────────────────────────────
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def generate(force: bool = False):
    if not os.path.exists(COMBINED):
        raise FileNotFoundError(f"{COMBINED} not found — run `python -m src.combine` first")

    src_hash = _sha256(COMBINED)
    if not force and os.path.exists(EMB_PATH) and os.path.exists(HASH_PATH):
        with open(HASH_PATH) as f:
            if f.read().strip() == src_hash:
                print(f"  Cache hit — embeddings up to date ({EMB_PATH})")
                return

    global_ids, translit_texts, commentary_texts = [], [], []
    with open(COMBINED, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            global_ids.append(rec["global_id"])
            translit_texts.append(rec.get("transliteration") or "")
            commentary_texts.append(rec.get("commentary") or "")

    N = len(global_ids)
    print(f"  Embedding {N} chunks × 2 fields ...")

    print("  [1/2] transliteration ...")
    t_emb = embedder.encode_passages(translit_texts)

    print("  [2/2] commentary ...")
    c_emb = embedder.encode_passages(commentary_texts)

    os.makedirs(os.path.dirname(EMB_PATH), exist_ok=True)
    np.savez_compressed(
        EMB_PATH,
        global_ids=np.array(global_ids),
        transliteration_emb=t_emb,
        commentary_emb=c_emb,
    )
    with open(HASH_PATH, "w") as f:
        f.write(src_hash)
    print(f"  Saved → {EMB_PATH}  ({t_emb.nbytes + c_emb.nbytes:,} bytes uncompressed)")


def load_embeddings() -> dict[str, dict[str, np.ndarray]]:
    """Returns {global_id: {'transliteration': vec, 'commentary': vec}}"""
    data = np.load(EMB_PATH, allow_pickle=True)
    return {
        str(gid): {
            "transliteration": data["transliteration_emb"][i],
            "commentary":      data["commentary_emb"][i],
        }
        for i, gid in enumerate(data["global_ids"])
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print("== Generating embeddings ==")
    generate(force=args.force)
