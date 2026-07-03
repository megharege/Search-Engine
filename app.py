"""
Streamlit search UI — run after completing the full pipeline.

    streamlit run app.py

MEILI_URL and MEILI_MASTER_KEY are read from environment (same as pipeline).
"""
import json, os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ayurveda Verse Search", layout="wide", page_icon="📜")

# ── cache heavy objects across reruns ────────────────────────────────────────
@st.cache_resource
def _load_embedder():
    from src.embed import embedder
    embedder.load()          # warms the GPU; cached for the session lifetime
    return embedder

@st.cache_resource
def _get_index():
    from src.search import get_index
    return get_index()

@st.cache_data
def _load_combined() -> pd.DataFrame:
    path = os.path.join(os.path.dirname(__file__), "data", "combined.jsonl")
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))
    except FileNotFoundError:
        pass
    return pd.DataFrame(rows)

# ── startup ───────────────────────────────────────────────────────────────────
_load_embedder()        # load model at app start, not on first search
df = _load_combined()

st.title("📜 Ayurveda Verse Search")

if df.empty:
    st.error("No data found. Run `python pipeline.py` first.")
    st.stop()

BOOKS = {
    "MN1": "Madhava Nidana - Part 1",
    "MN2": "Madhava Nidana - Part 2",
    "SUS": "Sushruta Samhita",
    "AH":  "Ashtanga Hridaya",
}

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Search Options")
    mode_label = st.radio("Mode", ["Hybrid", "Semantic", "Keyword"], horizontal=True,
                          help="Hybrid = semantic + keyword fusion (best for clinical queries)")
    embed_field = st.radio("Embed field", ["Commentary", "Transliteration"], horizontal=True,
                           help="Commentary = search by meaning; Transliteration = search by verse text")
    embedder_key = "commentary_embedder" if embed_field == "Commentary" else "transliteration_embedder"
    top_k = st.slider("Results", 3, 30, 10)

    st.divider()
    st.header("🔖 Filters")

    book_choices = st.multiselect(
        "Book", options=sorted(df["book_id"].unique()),
        format_func=lambda b: BOOKS.get(b, b),
    )
    scoped = df[df["book_id"].isin(book_choices)] if book_choices else df

    sthana_opts = sorted(scoped["sthana"].dropna().unique())
    sthana_choices = st.multiselect("Sthana (textual division)", options=sthana_opts)

    cat_opts = sorted(scoped["primary_category"].dropna().unique())
    primary_cat = st.multiselect("Primary category", options=cat_opts)

    all_tags = sorted({c for row in scoped["categories_found"] for c in (row or [])})
    tag_choices = st.multiselect("Category tags", options=all_tags)

    ch_col = scoped["chapter_number"].dropna()
    if not ch_col.empty and ch_col.min() < ch_col.max():
        ch_min, ch_max = int(ch_col.min()), int(ch_col.max())
        chapter_range = list(st.slider("Chapter range", ch_min, ch_max, (ch_min, ch_max)))
    else:
        chapter_range = None

    st.divider()
    with st.expander("🔑 Exact lookup by ID"):
        lk_book  = st.selectbox("Book", [""] + sorted(df["book_id"].unique()),
                                 format_func=lambda b: "—" if not b else BOOKS.get(b, b))
        lk_chunk = st.text_input("Chunk ID (e.g. AH_1)")
        lk_verse = st.text_input("Verse ID")
        do_lookup = st.button("Look up")


# ── result card ───────────────────────────────────────────────────────────────
def render(r: dict):
    book = BOOKS.get(r.get("book_id", ""), r.get("book_id", ""))
    with st.container(border=True):
        cols = st.columns([6, 1])
        with cols[0]:
            st.markdown(
                f"**{book}** &nbsp;·&nbsp; "
                f"Ch. {r.get('chapter_number')} &nbsp;·&nbsp; "
                f"*{r.get('chapter_title', '')}*"
            )
        with cols[1]:
            st.caption(f"`{r.get('book_id')}` `{r.get('chunk_id')}`")

        if r.get("topic_heading"):
            st.caption(f"📌 {r['topic_heading']}")

        if r.get("sanskrit_text"):
            st.markdown(f"> *{r['sanskrit_text']}*")

        if r.get("transliteration"):
            with st.expander("Transliteration"):
                st.code(r["transliteration"], language=None)

        st.write(r.get("commentary", ""))

        tags = r.get("categories_found") or []
        if tags:
            st.caption("  ".join(f"`{t}`" for t in tags))


# ── exact lookup ──────────────────────────────────────────────────────────────
if do_lookup:
    from src.search import lookup_verse
    hits = lookup_verse(
        chunk_id=lk_chunk or None,
        verse_id=lk_verse or None,
        book_id =lk_book  or None,
    )
    st.subheader(f"Lookup — {len(hits)} result(s)")
    for r in hits:
        render(r)

# ── main search ───────────────────────────────────────────────────────────────
query = st.text_input(
    "Search by symptom, disease, treatment, or partial shloka",
    placeholder="e.g. excessive thirst and frequent urination",
)

if query:
    from src.search import search_verses
    try:
        with st.spinner("Searching..."):
            hits = search_verses(
                query            = query,
                mode             = mode_label.lower(),
                embed_field      = embedder_key,
                top_k            = top_k,
                book_id          = book_choices   or None,
                sthana           = sthana_choices or None,
                primary_category = primary_cat    or None,
                categories_found = tag_choices    or None,
                chapter_range    = chapter_range,
            )
        st.subheader(f"{len(hits)} result(s)")
        for r in hits:
            render(r)
    except Exception as e:
        st.error(
            f"Search failed: {e}\n\n"
            "Make sure Meilisearch is running (`MEILI_URL` and `MEILI_MASTER_KEY` set)."
        )
