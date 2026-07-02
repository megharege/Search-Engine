# Ayurveda LLM Data & Pipeline Report
**Comprehensive Audit & Architecture Review**

---

## 1. Executive Summary
This report consolidates analysis passes run against the Ayurvedic text ingestion pipeline, including a chunk-level structural audit of the parsed JSONL files, a Gemma-2B token census across the corpus, and a field-level breakdown isolating Sanskrit, transliteration, commentary, and plain-English content. 

This document describes what successfully passed through OCR extraction and structuring, the state of the search engine architecture (Meilisearch + MCP), and where the parser still needs work before the corpus is fully reliable for RAG (Retrieval-Augmented Generation).

### High-Level Statistics
* **Source Texts Audited:** 8
* **Parsed Chunks:** 7,549
* **Chunks with a Real Shloka:** 7,235
* **Gemma-2B Tokens (Corpus-wide):** ~5.2M

### Key Findings
**Where the corpus is strong:**
* **Parser Reliability:** 95.8% of all parsed chunks (7,235 of 7,549) carry non-empty Sanskrit text. The parser reliably locates verse content across wildly different source layouts.
* **Identity Stability:** Chunk-ID collisions are **zero** across every book. The underlying identity hashing scheme is sound.
* **Verse Numbering:** Malformed verse numbering is essentially absent outside one text (Sharangadhara), meaning downstream citation and cross-referencing can safely lean on `verse_id`.

**Fail Points & Areas for Improvement:**
* **Uneven Field Coverage:** Transliteration and commentary coverage is uneven by design. Three books (Madhava Nidana, Sharangadhara, Sushruta Samhita) are missing one or both fields entirely, mostly due to OCR column-merging rather than missing source content.
* **Verse Splitting Logic:** Duplicate `verse_ids` within a chapter run as high as 48.8% (Sushruta Samhita) and 41.7% (Sharangadhara) — a strong signal that the verse-splitting logic is over- or under-segmenting in those parsers.
* **Coverage Discrepancies:** Token-level analysis covers 10 corpora (includes two Bhavaprakasa Nighantu volumes, B01/B02, tokenized separately) while the chunk-level structural audit covers 8. 

---

## 2. System Architecture & Processes

The Ayurveda Search Engine is built on a multi-tiered architecture designed for high-performance retrieval and LLM integration.

### Core Components
1. **Search Backend (Meilisearch):** Handles vector storage and hybrid (keyword + semantic) search. Configured with a 384-dimensional embedding model (`intfloat/multilingual-e5-small`).
2. **Main Frontend (Streamlit):** Provides an interactive UI for searching verses, with toggleable modes (Hybrid, Semantic, Keyword) and real-time LLM re-ranking using Gemini/Claude.
3. **Web API (FastAPI):** Serves a standalone HTML/JS website and provides a REST API (`/api/search`) for querying the index.
4. **Agentic Integration (FastMCP):** A Model Context Protocol (MCP) server that exposes the search index to AI assistants (like Claude) securely via SSE/HTTP transport with bearer auth.

### The Ingestion Pipeline
Source material arrives as loosely structured OCR text (Devanagari verse lines interleaved with commentary, inconsistent line breaks). Each book-specific converter turns this into structured records.

**Pipeline Flow:**
1. **Extraction:** OCR text is parsed into raw JSON lines.
2. **Transformation:** Data is mapped to the standard Chunk Schema (see below).
3. **Deduplication:** A unique `chunk_id` is generated using an MD5 hash of the composite key (`book + sthana + chapter + verse`).
4. **Embedding Generation:** The `generate_embeddings.py` script computes 384-dimensional vectors for the combined text (`topic_heading` + `transliteration` + `commentary`) using the `intfloat/multilingual-e5-small` model.
5. **Meilisearch Ingestion:** The `ingest.py` script uploads the finalized records (with vectors) into the Meilisearch index.

---

## 3. Input & Output Schema

The following schema is the strict contract every downstream converter targets, ensuring uniformity across irregular source OCRs.

### Chunk Schema (JSONL)
| Field | Type | Description |
|-------|------|-------------|
| `chunk_id` | String | MD5 hash of a composite key (book + sthana + chapter + verse). The stable identity for the chunk. |
| `sthana` | String | Section/book division, e.g., "Sutrasthana", "Nidana-Sthana". |
| `chapter_number` | Integer | Chapter number within the sthana. |
| `chapter_title` | String | Chapter title as recovered from the source, when present. |
| `verse_id` | String | Verse/shloka identifier, e.g., "1.12". |
| `topic_heading` | String | Sub-topic heading, where the source text carries one. |
| `sanskrit_text` | String | Original Devanagari / source-script text. |
| `transliteration` | String | IAST transliteration, generated via `indic_transliteration`. |
| `commentary` | String | Commentary / gloss text. Kept raw where OCR merged Sanskrit and Hindi. |
| `source_lines` | Array | Raw OCR lines the chunk was assembled from (for traceability). |
| `categories_found`| Array | All matched domain-keyword categories for the chunk. |
| `primary_category`| String | Single best-fit category assigned to the chunk. |
| `_vectors` | Object | Generated embeddings (e.g., `{"default": [...]}`) for Meilisearch vector search. |

---

## 4. Corpus-Wide Statistics

Eight source texts were run through the chunk-level structural audit, contributing a total of 7,549 chunks. 

*Note: Chunk count is not a proxy for content volume. Sharangadhara leads on chunk count but has zero commentary tokens, while Astanga Hridaya has a tenth of the chunks but the second-highest average commentary length.*

### Book-Level Summary
| Book | Chunks | Chapters | Shlokas | Avg Skt. Chars | Avg Comm. Chars | Top Category |
|------|--------|----------|---------|----------------|-----------------|--------------|
| Sharangadhara | 1,972 | 14 | 1,972 | 550.7 | 0.0 | dravya_guna |
| Bahavaprakasha Vol. 2 | 1,571 | 30 | 1,562 | 411.2 | 762.3 | pharmacology |
| Charaka Samhita | 1,558 | 29 | 1,549 | 414.7 | 769.6 | pharmacology |
| Bhavaprakasha Vol. 1 | 1,439 | 7 | 1,238 | 361.2 | 656.7 | properties |
| Madhava Nidana | 404 | 33 | 383 | 788.3 | 2,145.2 | dosha |
| Sushruta Samhita | 240 | 16 | 187 | 347.8 | 818.5 | diagnosis |
| Madhavanidanam | 239 | 31 | 237 | 1,365.6 | 2,217.4 | dosha |
| Astanga Hridaya | 126 | 31 | 107 | 1,356.1 | 3,408.6 | dosha |

---

## 5. Text Completeness & Structural Coverage

Sanskrit coverage is the strongest signal in the corpus — every book clears 77%, and five of eight clear 99%. Transliteration and commentary track which OCR source had cleanly separated columns vs. merged text.

### Coverage by Field
| Book | Total Chunks | Non-Blank Skt. | Blank Skt. | Non-Blank Translit. | Non-Blank Comm. | Blank Comm. |
|------|--------------|----------------|------------|---------------------|-----------------|-------------|
| Astanga Hridaya | 126 | 107 | 19 | 28 | 126 | 0 |
| Bahavaprakasha Vol. 2| 1,571 | 1,562 | 9 | 667 | 1,564 | 7 |
| Bhavaprakasha Vol. 1 | 1,439 | 1,238 | 201 | 321 | 1,115 | 324 |
| Charaka Samhita | 1,558 | 1,549 | 9 | 663 | 1,551 | 7 |
| Madhava Nidana | 404 | 383 | 21 | 0 | 404 | 0 |
| Madhavanidanam | 239 | 237 | 2 | 237 | 239 | 0 |
| Sharangadhara | 1,972 | 1,972 | 0 | 1,972 | 0 | 1,972 |
| Sushruta Samhita | 240 | 187 | 53 | 0 | 235 | 5 |

---

## 6. Verse Identification & Data Quality

Chunk-ID collisions are **zero** everywhere. The composite-key hashing scheme holds up across all books, meaning downstream deduplication and citation (including MCP tool lookups) can trust `chunk_id` as a stable primary key.

### Quality Flags by Book
| Book | `verse_id` Parsed | Dup. `verse_id` | Malformed | Short Shloka (<10ch) | Large Source Span (>100 ln) | Collisions |
|------|-------------------|-----------------|-----------|----------------------|-----------------------------|------------|
| Astanga Hridaya | 74.6% | 27 | 0 | 0 | 35 | 0 |
| Bahavaprakasha Vol. 2| 99.9% | 289 | 0 | 0 | 17 | 0 |
| Bhavaprakasha Vol. 1 | 59.1% | 254 | 0 | 3 | 0 | 0 |
| Charaka Samhita | 99.9% | 287 | 0 | 0 | 0 | 0 |
| Madhava Nidana | 84.9% | 47 | 0 | 1 | 0 | 0 |
| Madhavanidanam | 87.0% | 16 | 0 | 0 | 46 | 0 |
| Sharangadhara | 99.9% | 822 | 32 | 0 | 4 | 0 |
| Sushruta Samhita | 100.0%| 117 | 0 | 1 | 25 | 0 |

---

## 7. Category & Thematic Distribution

*Note: Category taxonomy is not identical across books. Category distributions are best read within a book rather than compared directly across the corpus.*

| Book | Top Primary Category | Top 5 Categories (All Tags) |
|------|----------------------|-----------------------------|
| Astanga Hridaya | dosha (54.0%) | dosha, food_diet, diagnosis, anatomy, treatment |
| Bahavaprakasha Vol. 2| pharmacology | pharmacology, diet_food, treatment, dosha, panchakarma |
| Bhavaprakasha Vol. 1 | properties | properties, treatment, pharmacognosy, dosha, general |
| Charaka Samhita | pharmacology | pharmacology, diet_food, treatment, dosha, panchakarma |
| Madhava Nidana | dosha | dosha, fever, nidana, digestion, respiratory |
| Madhavanidanam | dosha | dosha, ent, nidana_diagnosis, treatment, twak_roga_skin |
| Sharangadhara | dravya_guna | dravya_guna, rasashastra, kalpana_pharmaceutics, dosha, mana_paribhasha_measurement |
| Sushruta Samhita | vata (42.5%) | diagnosis, anatomy, disease, vata, pitta |

---

## 8. Global Field-Level Token Comparison (Gemma-2B)

The table below breaks down Gemma-2B token counts for Sanskrit, IAST transliteration, and commentary, plus a plain-regex English-word count run as a cross-check.

| Book | Field | Total Tokens | Avg Tokens | Min | Max |
|------|-------|--------------|------------|-----|-----|
| **Astanga Hridaya** | Sanskrit | 79,594 | 743.9 | 10 | 8,537 |
| | Transliteration | 1,417 | 50.6 | 21 | 176 |
| | Commentary | 112,147 | 897.2 | 2 | 11,944 |
| | English words | 66,372 | 531.0 | 1 | 6,588 |
| **B01** | Sanskrit | 106,936 | 218.7 | 3 | 5,486 |
| | Transliteration | 102,265 | 209.1 | 4 | 5,318 |
| | Commentary | 312,711 | 603.7 | 1 | 6,589 |
| **B02** | Sanskrit | 219,054 | 88.8 | 2 | 6,023 |
| | Transliteration | 215,652 | 87.4 | 1 | 5,788 |
| | Commentary | 136,619 | 59.9 | 1 | 5,176 |
| **Bahavaprakasha Vol. 2** | Sanskrit | 341,082 | 218.9 | 8 | 2,522 |
| | Transliteration | 55,049 | 82.5 | 5 | 13,371 |
| | Commentary | 372,702 | 238.8 | 8 | **96,814** |
| **Bhavaprakasha Vol. 1** | Sanskrit | 234,650 | 189.7 | 3 | 3,739 |
| | Transliteration | 20,372 | 77.5 | 4 | 1,171 |
| | Commentary | 188,723 | 205.1 | 2 | 2,560 |
| **Charaka Samhita** | Sanskrit | 341,081 | 220.8 | 8 | 2,522 |
| | Transliteration | 54,558 | 82.3 | 5 | 13,165 |
| | Commentary | 373,253 | 241.1 | 8 | **97,047** |
| **Madhava Nidana** | Sanskrit | 158,925 | 416.0 | 21 | 5,348 |
| | Transliteration | 0 | 0.0 | 0 | 0 |
| | Commentary | 233,345 | 580.5 | 21 | 5,943 |
| **Madhavanidanam** | Sanskrit | 166,594 | 727.5 | 55 | 4,538 |
| | Transliteration | 164,499 | 718.3 | 53 | 4,623 |
| | Commentary | 138,529 | 599.7 | 36 | 4,291 |
| **Sharangadhara** | Sanskrit | 460,903 | 240.2 | 14 | 26,811 |
| | Transliteration | 506,158 | 263.8 | 12 | **27,160** |
| | Commentary | 0 | 0.0 | 0 | 0 |
| **Sushruta Samhita** | Sanskrit | 35,441 | 189.5 | 2 | 1,011 |
| | Transliteration | 0 | 0.0 | 0 | 0 |
| | Commentary | 51,497 | 242.9 | 3 | 3,334 |

> **Context Window Warning:** Bahavaprakasha Vol. 2 and Charaka Samhita both carry a single commentary outlier near **97,000 tokens**. Sharangadhara has transliteration chunks over **27,000 tokens**. These will exceed LLM context windows and cause Meilisearch payload size errors unless sub-chunked.

---

## 9. Appendix — Pre-Structuring Pass: Sushruta Samhita
An earlier exploratory pass directly against the raw Markdown source for Sushruta Samhita yielded 420 chunks (SC1–SC420) from 4,070 source lines.

| Metric | Value |
|--------|-------|
| Average chunk size | 707 characters (median 218) |
| Chunk size range | 0 – 40,095 characters |
| Unique chapters detected (H2) | 322 |
| Chunks containing lists | 119 (28.3%) |
| Heading hierarchy | H1 (book) > H2 (chapter) > H3 (section) |

---

## 10. Embedding Coverage

A separate embedding pass (`generate_embeddings.py`) produced dense vector representations ahead of full-corpus retrieval indexing into Meilisearch.

### Embedding Set Summary
* **Chunks Embedded:** 1,378 chunks embedded out of the 7,549 (~18.3% of the corpus) covering a working subset of 4 source texts.
* **Vector Specs:** 1024-dimensional float32 vector (from previous iterations) / 384-dimensional `intfloat/multilingual-e5-small` in current iteration.
* **Storage:** Embedded directly into the `_vectors` field inside `merged_books_with_embeddings.jsonl` prior to Meilisearch indexing.

### Books Covered So Far (Subset)
| Book | Chunks Embedded | Share of Subset |
|------|-----------------|-----------------|
| Sushruta Samhita (SUS) | 382 | 27.7% |
| Madhava Nidana, Vol. 1 (MN1) | 367 | 26.6% |
| Astanga Hridaya (AH) | 331 | 24.0% |
| Madhava Nidana, Vol. 2 (MN2) | 298 | 21.6% |

*(Note: The remaining four texts require verse boundary validation before embedding due to high duplicate rates).*

---

## 11. Observations & Recommendations

### 1. Coverage Discrepancy (8 vs. 10 Corpora)
The chunk-level structural audit covers 8 books (7,549 chunks), while the token-level audit covers 10 corpora (including B01 and B02 — likely Bhavaprakasa Nighantu Part 1/2). 
**Recommendation:** Run the structural EDA pass on B01/B02 so coverage, verse-ID quality, and category tagging can be assessed on the same basis.

### 2. Highest-Priority Parser Fixes
* **Verse Logic:** Sushruta Samhita and Sharangadhara have high duplicate-verse rates (48.8% / 41.7%). Investigate if verse-splitting logic is resetting/repeating counters across sub-sections.
* **Source Quality:** Bhavaprakasha Vol. 1 has weaker coverage (86.0% Sanskrit, 59.1% verse_id parse). Conduct a manual sample review to confirm if this is a source-scan issue or a converter gap.
* **Missing Fields:** Madhava Nidana and Sushruta Samhita's zero transliteration coverage is likely a configuration gap (IAST generation disabled) rather than a source limitation.

### 3. Sub-Chunking for RAG
The token outliers identified in Section 8 (chunks of 97k and 27k tokens) **must be sub-chunked** before ingestion. They will crash API gateways, hit Meilisearch HTTP payload limits, and easily blow past standard LLM reranker context windows if retrieved in a RAG pipeline.
