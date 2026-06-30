"""
QDRANT BUILD (parallel to MeiliSearch)
Pure vector semantic search — better for meaning-first queries.

Usage:
    python 7_qdrant_build.py --input corpus_tagged.jsonl
    python 7_qdrant_build.py --query "vata dosha treatment"

Install:
    pip install qdrant-client sentence-transformers
    docker run -p 6333:6333 qdrant/qdrant
"""

import json
import argparse

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    from sentence_transformers import SentenceTransformer
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("[warn] pip install qdrant-client sentence-transformers")

QDRANT_URL = "localhost"
QDRANT_PORT = 6333
COLLECTION = "ayurveda"
MODEL_NAME = "intfloat/multilingual-e5-small"
VECTOR_SIZE = 384


def get_client():
    return QdrantClient(QDRANT_URL, port=QDRANT_PORT)


def index_documents(jsonl_path: str):
    if not QDRANT_AVAILABLE:
        return

    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    with open(jsonl_path, encoding="utf-8") as f:
        chunks = [json.loads(l) for l in f if l.strip()]
    print(f"Loaded {len(chunks)} chunks")

    client = get_client()

    # Create collection
    try:
        client.get_collection(COLLECTION)
        print(f"Collection '{COLLECTION}' exists. Deleting and recreating.")
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    client.create_collection(
        COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    )
    print(f"Collection '{COLLECTION}' created.")

    # Build text to embed: transliteration + commentary (skip pure Sanskrit for embedding)
    texts = []
    for c in chunks:
        text = " ".join(filter(None, [
            c.get("topic_heading", ""),
            c.get("transliteration", ""),
            c.get("commentary", "")[:500]
        ]))
        texts.append(text)

    print("Encoding vectors (this may take a few minutes)...")
    vectors = model.encode(texts, batch_size=32, show_progress_bar=True)

    # Upload in batches
    BATCH = 200
    for i in range(0, len(chunks), BATCH):
        batch_chunks = chunks[i:i + BATCH]
        batch_vectors = vectors[i:i + BATCH]

        points = []
        for j, (chunk, vec) in enumerate(zip(batch_chunks, batch_vectors)):
            # Qdrant needs integer or UUID ids
            point_id = i + j
            payload = {k: v for k, v in chunk.items() if isinstance(v, (str, int, float, list, bool, type(None)))}
            points.append(PointStruct(id=point_id, vector=vec.tolist(), payload=payload))

        client.upload_points(COLLECTION, points)
        print(f"  Uploaded {min(i + BATCH, len(chunks))}/{len(chunks)}")

    info = client.get_collection(COLLECTION)
    print(f"\nDone. Vectors in collection: {info.vectors_count}")


def search_qdrant(
    query: str,
    *,
    dosha: str = None,
    sthana: str = None,
    top_k: int = 10
) -> list[dict]:
    if not QDRANT_AVAILABLE:
        return []

    model = SentenceTransformer(MODEL_NAME)
    client = get_client()

    query_vector = model.encode(query).tolist()

    # Build optional filter
    must_conditions = []
    if dosha:
        must_conditions.append(FieldCondition(key="dosha", match=MatchValue(value=dosha)))
    if sthana:
        must_conditions.append(FieldCondition(key="sthana", match=MatchValue(value=sthana)))

    qdrant_filter = Filter(must=must_conditions) if must_conditions else None

    results = client.search(
        collection_name=COLLECTION,
        query_vector=query_vector,
        query_filter=qdrant_filter,
        limit=top_k,
        with_payload=True
    )

    hits = []
    for r in results:
        hit = dict(r.payload)
        hit["qdrant_score"] = r.score
        hits.append(hit)

    return hits


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="corpus_tagged.jsonl")
    parser.add_argument("--query", default=None)
    parser.add_argument("--dosha", default=None)
    parser.add_argument("--index", action="store_true", help="Index documents")
    args = parser.parse_args()

    if args.index:
        index_documents(args.input)

    if args.query:
        print(f"\nSearching Qdrant: '{args.query}'")
        hits = search_qdrant(args.query, dosha=args.dosha)
        for i, h in enumerate(hits, 1):
            score = h.get("qdrant_score", 0)
            print(f"{i}. [{score:.3f}] {h.get('chunk_id')} — {h.get('topic_heading','')}")
            comm = h.get("commentary", "")
            if comm:
                print(f"   {comm[:120]}...")
