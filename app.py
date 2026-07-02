import streamlit as st
import meilisearch
import os
from dotenv import load_dotenv
load_dotenv()

# Configure Page
st.set_page_config(
    page_title="Ayurveda Verse Search",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to match the original UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Inter:wght@400;500;600&display=swap');

    /* Global Dark Theme */
    .stApp {
        background-color: #0a0e17;
        background-image: 
            radial-gradient(at 0% 0%, rgba(20, 40, 60, 0.5) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(20, 60, 40, 0.3) 0px, transparent 50%);
        background-attachment: fixed;
        color: #f1f5f9;
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: rgba(20, 26, 40, 0.6) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    [data-testid="stSidebar"] * {
        color: #f1f5f9 !important;
    }
    
    /* Headers */
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif !important;
    }
    
    .sidebar-logo {
        font-family: 'Outfit', sans-serif;
        font-size: 24px;
        font-weight: 700;
        line-height: 1.2;
        background: linear-gradient(to right, #4ade80, #38bdf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
    }
    .sidebar-logo span {
        font-weight: 300;
        font-size: 20px;
    }
    
    /* Custom Result Card */
    .verse-card {
        background: rgba(25, 33, 50, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 28px;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
        margin-bottom: 24px;
    }
    .verse-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: #4ade80;
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    .verse-card:hover {
        background: rgba(32, 41, 62, 0.8);
        transform: translateY(-2px);
        box-shadow: 0 12px 24px -10px rgba(0, 0, 0, 0.4);
    }
    .verse-card:hover::before {
        opacity: 1;
    }
    .verse-meta {
        font-size: 12px;
        color: #38bdf8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 12px;
        font-weight: 600;
    }
    .verse-topic {
        font-family: 'Outfit', sans-serif;
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 16px;
        color: #fff;
    }
    .verse-sanskrit {
        font-size: 18px;
        color: #e2e8f0;
        margin-bottom: 12px;
        line-height: 1.8;
    }
    .verse-translit {
        font-family: monospace;
        font-size: 14px;
        color: #94a3b8;
        margin-bottom: 16px;
        padding-bottom: 16px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .verse-commentary {
        font-size: 15px;
        color: #cbd5e1;
        line-height: 1.7;
        margin-bottom: 20px;
    }
    .verse-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    .tag {
        background: rgba(255,255,255,0.05);
        color: #94a3b8;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        border: 1px solid rgba(255,255,255,0.05);
    }
    mark {
        background-color: rgba(56, 189, 248, 0.2);
        color: #7dd3fc;
        padding: 0 2px;
        border-radius: 2px;
        box-shadow: 0 0 4px rgba(56, 189, 248, 0.2);
    }
    
    /* Search Bar Input styling */
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border-radius: 12px;
        padding: 15px 20px;
    }
    .stTextInput > div > div > input:focus {
        border-color: #4ade80 !important;
        box-shadow: 0 0 0 4px rgba(74, 222, 128, 0.1) !important;
    }
    
    /* Stats Text */
    .search-stats {
        font-size: 13px;
        color: #94a3b8;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "search_memory" not in st.session_state:
    st.session_state.search_memory = []

if "search_query" not in st.session_state:
    st.session_state.search_query = ""

from search_core import hybrid_search, get_available_texts

# ── Load embedding model ONCE, shared across all sessions ────────────────────
@st.cache_resource(show_spinner="Loading AI model (first time only)...")
def load_embed_model():
    import os
    import torch
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    # Disable torch lazy initialization to avoid meta tensor errors in Streamlit
    torch.set_default_device("cpu")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(
        "intfloat/multilingual-e5-small",
        device="cpu"
    )
    # Force full weight materialization with a warmup pass
    _ = model.encode("warmup", show_progress_bar=False, convert_to_numpy=True)
    return model

embed_model = load_embed_model()

# Sidebar UI
with st.sidebar:
    st.markdown('<div class="sidebar-logo">Ayurveda<br/><span>Explorer</span></div>', unsafe_allow_html=True)
    
    st.markdown("### SEARCH MODE")
    mode = st.radio("Select Mode", ["Hybrid", "Semantic", "Keyword"], index=0, label_visibility="collapsed")
    
    st.markdown("### BOOKS")
    all_books = ["Sushruta Samhita", "Ashtanga Hridaya", "Madhavanisana Pt1", "Madhavanisana Pt2"]
    selected_books = []
    for book in all_books:
        if st.checkbox(book, value=False):
            selected_books.append(book)
            
    st.markdown("### RESULTS LIMIT")
    limit = st.slider("Limit", min_value=5, max_value=100, value=45, step=5, label_visibility="collapsed")
    
    st.markdown("### SEARCH MEMORY")
    if st.session_state.search_memory:
        if st.button("Clear Memory", key="clear_mem"):
            st.session_state.search_memory = []
            st.rerun()
            
        for idx, mem_query in enumerate(reversed(st.session_state.search_memory[-5:])):
            if st.button(mem_query, key=f"mem_{idx}"):
                st.session_state.search_query = mem_query
    else:
        st.caption("No recent searches.")
        
    st.markdown("<br><br><p style='font-size: 12px; color: rgba(255, 255, 255, 0.3); text-align: center;'>Powered by AI & search_core</p>", unsafe_allow_html=True)

# Main Content
st.title("")

def update_search():
    st.session_state.search_query = st.session_state.search_input_widget

query = st.text_input("", placeholder="Search verses, e.g. vata dosha jwara treatment...", 
                      key="search_input_widget", 
                      value=st.session_state.search_query, 
                      on_change=update_search)

# Add to memory if new
current_query = st.session_state.search_query.strip()
if current_query and (not st.session_state.search_memory or st.session_state.search_memory[-1] != current_query):
    st.session_state.search_memory.append(current_query)

if not current_query:
    pass
elif current_query:
    with st.spinner("Searching ancient texts..."):
        try:
            import time
            start = time.time()
            hits = hybrid_search(query=current_query, limit=limit, mode=mode, embed_model=embed_model)
            time_ms = int((time.time() - start) * 1000)
            
            if not hits:
                st.markdown('<div style="text-align:center; color:#94a3b8; padding: 40px;"><h3>No verses found</h3><p>Try adjusting your search query or removing filters.</p></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="search-stats">Found {len(hits)} results in {time_ms}ms (Hybrid + LLM)</div>', unsafe_allow_html=True)
                
                for i, hit in enumerate(hits, 1):
                    fmt = hit.get("_formatted", hit)
                    source = hit.get("source_file", "Unknown Book")
                    sthana = hit.get("sthana", "")
                    ch_num = hit.get("chapter_number", "")
                    ch_title = hit.get("chapter_title", "")
                    verse_id = hit.get("verse_id", "")
                    
                    topic = fmt.get("topic_heading", "") or hit.get("topic_heading", "")
                    sanskrit = hit.get("sanskrit_text", "")
                    translit = fmt.get("transliteration", "") or hit.get("transliteration", "")
                    comment = fmt.get("commentary", "") or hit.get("commentary", "")
                    
                    header_parts = [source.upper()]
                    if sthana: header_parts.append(sthana.upper())
                    if ch_title: header_parts.append(f"CH. {ch_num} \"{ch_title.upper()}\"")
                    if verse_id: header_parts.append(f"VERSE {verse_id}")
                    meta_str = ' · '.join(header_parts)
                    
                    tags = set()
                    if hit.get("primary_category"): tags.add(hit.get("primary_category"))
                    if hit.get("categories_found"): tags.update(hit.get("categories_found"))
                    tags_html = "".join([f'<span class="tag">{t}</span>' for t in tags])
                    
                    card_html = f"""
                    <div class="verse-card">
                        <div class="verse-meta">#{i} &nbsp; {meta_str} (Score: {hit.get('score', 0):.2f})</div>
                        {f'<div class="verse-topic">{topic}</div>' if topic else ''}
                        {f'<div class="verse-sanskrit">{sanskrit}</div>' if sanskrit else ''}
                        {f'<div class="verse-translit">{translit}</div>' if translit else ''}
                        {f'<div class="verse-commentary">{comment}</div>' if comment else ''}
                        {f'<div class="verse-tags">{tags_html}</div>' if tags_html else ''}
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                        
        except Exception as e:
            st.error(f"Error querying backend: {e}")
else:
    st.markdown('<div style="text-align:center; color:#94a3b8; padding: 40px;"><h3>Explore Ancient Wisdom</h3><p>Enter a query above to search through classical Ayurvedic texts.</p></div>', unsafe_allow_html=True)
