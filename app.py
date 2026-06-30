"""
AYURVEDA VERSE SEARCH UI
Matches the layout in the screenshot: left sidebar (engine toggle, search mode,
book filter, sthana, chapter slider, category filter), main panel with verse cards.

Run:
    pip install streamlit meilisearch qdrant-client sentence-transformers
    streamlit run app.py --server.port 8501
"""

import streamlit as st
import json
import meilisearch
import time

st.set_page_config(page_title="Ayurveda Verse Search", layout="wide", initial_sidebar_state="expanded")

MEILI_URL = "http://localhost:7700"
MEILI_KEY = "ayurveda-dev-key"
INDEX_NAME = "ayurveda"

BOOK_OPTIONS = [
    "Sushruta Samhita",
    "Bhavaprakasa Nighantu",
    "Madhavanidanam",
    "Sharangadhara Samhita",
]

# ─────────────────────── Dark theme CSS ───────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .verse-card {
        background: #1a1d27;
        border: 1px solid #2d313f;
        border-radius: 8px;
        padding: 18px 22px;
        margin-bottom: 16px;
    }
    .verse-meta { color: #9aa0ad; font-size: 0.85rem; margin-bottom: 6px; }
    .verse-topic { color: #e8e8e8; font-weight: 600; font-size: 1.05rem; margin-bottom: 10px; }
    .sanskrit { font-size: 1.15rem; color: #f0f0f0; margin-bottom: 8px; line-height: 1.8; }
    .translit { color: #5fb3a3; font-family: monospace; font-size: 0.88rem; margin-bottom: 10px; }
    .translation { color: #d0d0d0; margin-bottom: 10px; line-height: 1.6; }
    .tag {
        display: inline-block; background: #21262f; color: #7fcdcd;
        border-radius: 4px; padding: 2px 8px; margin-right: 6px; font-size: 0.78rem;
    }
    .score { color: #6b7280; font-size: 0.8rem; margin-top: 8px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────── Sidebar ───────────────────────
with st.sidebar:
    st.markdown("## Engine")
    st.markdown("**Search backend**")
    backend = st.radio("backend", ["Qdrant", "Meilisearch"], label_visibility="collapsed", horizontal=False)

    st.markdown("**Search mode**")
    mode = st.radio("mode", ["Hybrid", "Semantic", "Keyword"], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("## Upload Books")
    uploaded_files = st.file_uploader(
        "Upload JSONL files (one per book)",
        type=["jsonl"],
        accept_multiple_files=True,
        help="Each file becomes a book option in the filter below"
    )
    if uploaded_files:
        if st.button("Index uploaded files"):
            with st.spinner("Indexing..."):
                client = meilisearch.Client(MEILI_URL, MEILI_KEY)
                index = client.index(INDEX_NAME)
                for uf in uploaded_files:
                    book_name = uf.name.replace(".jsonl", "").replace("_", " ").title()
                    lines = uf.read().decode("utf-8").splitlines()
                    chunks = []
                    for line in lines:
                        if not line.strip():
                            continue
                        c = json.loads(line)
                        c["chunk_id"] = str(c.get("chunk_id", "")).replace(".", "_").replace("/", "_")
                        c["source_file"] = book_name
                        for f in ["sanskrit_text", "transliteration", "commentary", "topic_heading"]:
                            if c.get(f) is None:
                                c[f] = ""
                        chunks.append(c)
                    task = index.add_documents(chunks, primary_key="chunk_id")
                    st.success(f"{book_name}: {len(chunks)} verses queued (task {task.task_uid})")
                st.info("Refresh after a few seconds once indexing completes.")

    st.markdown("---")
    st.markdown("## Filters")

    st.markdown("**Book**")
    selected_books = st.multiselect("book", BOOK_OPTIONS, default=[], label_visibility="collapsed")

    st.markdown("**Sthana**")
    sthana_filter = st.selectbox(
        "sthana",
        ["All", "Sutrasthana", "Nidanasthana", "Sharirasthana", "Chikitsasthana", "Kalpasthana", "Uttaratantra"],
        label_visibility="collapsed"
    )

    st.markdown("**Chapter number**")
    chapter_range = st.slider("chapter", 1, 40, (1, 40), label_visibility="collapsed")

    st.markdown("**Primary category (topic tag)**")
    category_filter = st.multiselect(
        "category",
        ["general", "dosha", "nidana", "chikitsa", "dravyaguna", "rasayana"],
        label_visibility="collapsed"
    )

# ─────────────────────── Main panel ───────────────────────
st.markdown("### Ayurveda Verse Search")
query = st.text_input("Search", placeholder="e.g. vata dosha jwara treatment", label_visibility="collapsed")

alpha = {"Keyword": 0.0, "Hybrid": 0.5, "Semantic": 1.0}[mode]


def build_filter():
    parts = []
    if selected_books:
        book_clause = " OR ".join([f'source_file = "{b}"' for b in selected_books])
        parts.append(f"({book_clause})")
    if sthana_filter != "All":
        parts.append(f'sthana = "{sthana_filter}"')
    if category_filter:
        cat_clause = " OR ".join([f'primary_category = "{c}"' for c in category_filter])
        parts.append(f"({cat_clause})")
    parts.append(f"chapter_number >= {chapter_range[0]} AND chapter_number <= {chapter_range[1]}")
    return " AND ".join(parts)


@st.cache_resource
def get_meili_index():
    client = meilisearch.Client(MEILI_URL, MEILI_KEY)
    return client.index(INDEX_NAME)


def search_meili(q, alpha, filter_str, top_k=20):
    index = get_meili_index()
    params = {
        "limit": top_k,
        "attributesToHighlight": ["commentary", "transliteration", "topic_heading"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
    }
    if alpha > 0:
        params["hybrid"] = {"semanticRatio": alpha, "embedder": "default"}
    if filter_str:
        params["filter"] = filter_str
    start = time.time()
    result = index.search(q, params)
    elapsed = time.time() - start
    return result.get("hits", []), elapsed


if query:
    filter_str = build_filter()
    with st.spinner("Searching..."):
        hits, elapsed = search_meili(query, alpha, filter_str)

    st.caption(f"{len(hits)} results in {elapsed*1000:.0f}ms · backend: {backend} · mode: {mode}")

    for h in hits:
        meta = f"{h.get('source_file','')} · Ch. {h.get('chapter_number','')} \"{h.get('chapter_title','')}\" · Verse {h.get('verse_id','')}"
        tags = []
        if h.get("primary_category"):
            tags.append(h["primary_category"])
        tags.extend(h.get("categories_found", []))

        card = f"""
        <div class="verse-card">
            <div class="verse-meta">{meta}</div>
            <div class="verse-topic">{h.get('topic_heading','')}</div>
            <div class="sanskrit">{h.get('sanskrit_text','')}</div>
            <div class="translit">{h.get('transliteration','')}</div>
            <div class="translation">{h.get('commentary','')[:500]}</div>
            <div>{''.join(f'<span class="tag">{t}</span>' for t in tags)}</div>
            <div class="score">score: {h.get('_rankingScore', 0):.3f}</div>
        </div>
        """
        st.markdown(card, unsafe_allow_html=True)
else:
    st.info("Enter a search query above, or upload JSONL files in the sidebar to get started.")
