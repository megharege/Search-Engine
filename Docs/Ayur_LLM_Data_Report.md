# Ayurveda LLM Data & Pipeline Report
**Comprehensive Audit & Architecture Review**

---

## 1. Executive Summary
This report consolidates analysis passes run against the Ayurvedic text ingestion pipeline, including a chunk-level structural audit of the parsed JSONL files, a Gemma-4B token census across the corpus, and a field-level breakdown isolating Sanskrit, transliteration, commentary, and plain-English content. 

This document describes what successfully passed through OCR extraction and structuring, the state of the search engine architecture (Meilisearch + MCP), and where the parser still needs work before the corpus is fully reliable for RAG (Retrieval-Augmented Generation).

### High-Level Statistics
* **Source Texts Audited:** 8
* **Parsed Chunks:** 7,549
* **Chunks with a Real Shloka:** 7,235
* **Gemma-4B Tokens (Corpus-wide):** ~467K

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

## 8. Global Field-Level Token Comparison (Gemma-4B)

The table below breaks down Gemma-4B token counts for Sanskrit, IAST transliteration, and commentary, plus a plain-regex English-word count run as a cross-check.

| Book | Field | Total Tokens | Avg Tokens | Min | Max |
|------|-------|--------------|------------|-----|-----|
| **Ashtanga Hridaya** | Sanskrit | 68,436 | 206.8 | 17 | 1,042 |
| | Transliteration | 67,211 | 203.1 | 15 | 1,018 |
| | Commentary | 88,635 | 267.8 | 15 | 1,272 |
| | English words | 59,650 | 180.2 | 9 | 875 |
| **Madhava Nidana - Part 1** | Sanskrit | 27,482 | 74.9 | 12 | 388 |
| | Transliteration | 26,809 | 73.0 | 11 | 379 |
| | Commentary | 35,541 | 96.8 | 31 | 400 |
| | English words | 25,743 | 70.1 | 22 | 301 |
| **Madhava Nidana - Part 2** | Sanskrit | 22,145 | 74.3 | 15 | 457 |
| | Transliteration | 21,840 | 73.3 | 15 | 427 |
| | Commentary | 23,217 | 77.9 | 18 | 298 |
| | English words | 15,660 | 52.6 | 11 | 208 |
| **Sushruta Samhita** | Sanskrit | 30,406 | 79.6 | 12 | 429 |
| | Transliteration | 29,452 | 77.1 | 13 | 425 |
| | Commentary | 26,311 | 68.9 | 9 | 354 |
| | English words | 18,697 | 48.9 | 6 | 260 |

> **Context Window Warning:** Token counts have been updated for Gemma-4B tokenizer based on available corpora. Prior outliers were not present in this dataset subset.

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
