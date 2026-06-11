# Weekly Product Review Pulse — Implementation Plan

Phase-wise build plan with exit criteria, referencing [architecture.md](architecture.md) and [problemStatement.md](problemStatement.md).

---

## Phase 0 — Project Skeleton & Configuration

### Scope
- Create repository layout (`pulse/`, `config/`, `docs/`, `data/`)
- Set up `config/products/groww.yaml` and `config/pipeline.yaml`
- Create data models (`Review`, `RawReview` in `pulse/ingestion/models.py`)
- Create `.env.example` with all required environment variables
- Create documentation (`problemStatement.md`, `architecture.md`, `implementation-plan.md`, `edge-cases.md`)

### Exit Criteria
- [x] Directory structure matches architecture §4
- [x] Product config for Groww is valid YAML with all fields
- [x] Pipeline config has embedding, clustering, summarization, and safety sections
- [x] Data models are importable
- [x] All docs are present and consistent

---

## Phase 1 — Ingestion & Normalization

### Scope
- `pulse/ingestion/play_store.py` — Scrape Google Play reviews using `google-play-scraper`
- `pulse/ingestion/normalizer.py` — Quality filters: ≥8 words, English-only, no emoji
- `pulse/ingestion/cache.py` — Save `reviews_raw.json`, `reviews_normalized.json`, `manifest.json` under `data/cache/{product}/{date}/`
- Deduplication by hash of `(text, rating, published_at)`

### Exit Criteria
- [x] `fetch_play_store_reviews("com.nextbillion.groww", 10)` returns `list[RawReview]`
- [x] `normalize_reviews(raw)` filters to ~17% of raw (≥8 words, no emoji)
- [x] Cache files are written and can be loaded back
- [x] Running ingestion twice for the same product/date uses cached data or deduplicates

---

## Phase 2 — Analysis Pipeline (Embedding, Clustering, PII)

### Scope
- `pulse/pipeline/scrubber.py` — PII redaction (email → `[EMAIL]`, phone → `[PHONE]`, Aadhaar/PAN → `[ID]`)
- `pulse/pipeline/embeddings.py` — OpenAI `text-embedding-3-small` with batch processing
- `pulse/pipeline/clustering.py` — UMAP (n_neighbors=15, n_components=5, random_state=42) + HDBSCAN (min_cluster_size=5, min_samples=3)
- Cluster ranking: `score = size × (6 − avg_rating)`
- Noise cluster (label = −1) excluded

### Configuration
- Embedding model: OpenAI `text-embedding-3-small` (`OPENAI_API_KEY`)
- UMAP/HDBSCAN parameters from `config/pipeline.yaml`

### Exit Criteria
- [x] PII scrubber redacts emails, phone numbers, and long numeric sequences
- [x] Embeddings are generated in batches of 64
- [x] UMAP + HDBSCAN produces clusters ranked by score
- [x] Reviews with <20 normalized entries abort the run

---

## Phase 3 — LLM Summarization & Quote Validation

### Scope
- `pulse/pipeline/summarizer.py` — Groq `llama-3.3-70b-versatile`, one request per cluster, sequential with ≥2s interval
- `pulse/pipeline/quote_validator.py` — Case-insensitive substring match against scrubbed review texts
- Per-cluster JSON output: `theme_name`, `summary`, `quotes[]`, `action_ideas[]`

### Groq Limits
| Limit | Value | Implication |
|-------|-------|-------------|
| Requests/min | 30 | ≥2s between requests |
| Requests/day | 1,000 | ~10 req/run |
| Tokens/min | 12,000 | Pre-flight estimate <10K |
| Tokens/day | 100,000 | Cap `max_tokens_per_run` at 12,000 |

### Exit Criteria
- [x] Each top cluster produces a valid JSON theme object
- [x] Hallucinated quotes are dropped; themes with no valid quotes logged
- [x] Groq rate limits are respected (≥2s between calls)
- [x] Total tokens per run stay under 12K budget

---

## Phase 4 — Google Docs Delivery via MCP

### Scope
- `pulse/render/doc_section.py` — Build plain-text section content for Google Docs
- `pulse/agent/mcp_client.py` — HTTP client calling external MCP server (`POST /append_to_doc`)
- Update `pulse/cli.py` — Wire render + MCP client for real Doc delivery

### MCP Server
External server at [mcp-server-saksham](https://github.com/saksham20189575/mcp-server-saksham/):
- Endpoint: `POST /append_to_doc`
- Inputs: `doc_id` (string), `content` (string)
- The server handles Google OAuth internally

### Section Format
```
Groww — Weekly Review Pulse — 2026-W23
Period: Last 10 weeks (rolling) · Source: Google Play Store · Generated: 2026-06-08 IST

Top Themes
• Theme name — Summary

Real User Quotes
• "Exact validated quote"

Action Ideas
• Idea title — Detail

Who This Helps
• Product — Prioritize roadmap from recurring themes
• Support — Spot repeating complaints and quality issues
• Leadership — Fast health snapshot tied to customer voice
```

### Exit Criteria
- [x] `doc_section.build_section()` produces well-formatted plain-text
- [x] `mcp_client.append_to_doc()` successfully calls the MCP server
- [x] Ledger records `google_doc` delivery with external_id and URL
- [x] `--dry-run` skips the MCP call

---

## Phase 5 — Gmail Delivery via MCP

### Scope
- `pulse/render/email_teaser.py` — Build HTML email body with theme bullets + CTA link
- `pulse/agent/mcp_client.py` — Add `create_email_draft()` calling `POST /create_email_draft`
- Update `pulse/cli.py` — Wire email render + MCP client for Gmail delivery

### MCP Server
- Endpoint: `POST /create_email_draft`
- Inputs: `to` (string), `subject` (string), `body` (string)

### Email Format
- **Subject:** `Groww Weekly Review Pulse — 2026-W23`
- **Body:** Theme bullets + "Read full report" CTA link + footer
- **Default mode:** `draft` (configurable)

### Exit Criteria
- [x] `email_teaser.build_teaser()` produces HTML body with theme list and CTA
- [x] `mcp_client.create_email_draft()` successfully calls the MCP server
- [x] Ledger records `gmail` delivery with draft_id and idempotency key
- [x] `--dry-run` skips the MCP call

---

## Summary

| Phase | Status | Key Module |
|-------|--------|------------|
| Phase 0 — Skeleton & Config | ✅ Complete | `config/`, `docs/`, models |
| Phase 1 — Ingestion | ✅ Complete | `pulse/ingestion/` |
| Phase 2 — Pipeline | ✅ Complete | `pulse/pipeline/` (embed, cluster, scrub) |
| Phase 3 — Summarization | ✅ Complete | `pulse/pipeline/` (summarizer, validator) |
| Phase 4 — Google Docs MCP | ✅ Complete | `pulse/render/doc_section.py`, `pulse/agent/mcp_client.py` |
| Phase 5 — Gmail MCP | ✅ Complete | `pulse/render/email_teaser.py`, `pulse/agent/mcp_client.py` |
