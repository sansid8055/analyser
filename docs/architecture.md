# Weekly Product Review Pulse — Architecture

This document describes the technical architecture for the Groww Play Store review pulse: components, data flows, MCP integration, idempotency, and operational concerns. It extends [problemStatement.md](problemStatement.md).

## 1. Goals and Constraints

| Goal | Architectural Implication |
|------|--------------------------|
| Weekly insight report from Play Store reviews | Batch pipeline, not streaming |
| Google Doc as system of record | Append-only sections with stable anchors |
| Email as notification, not duplicate report | Teaser + deep link to Doc heading |
| MCP-only delivery to Google Workspace | Pulse agent never holds Google OAuth or calls REST directly |
| Idempotent weekly runs | Run ledger + deterministic section keys |
| Auditable history | Persist run metadata and delivery IDs |
| Safe LLM usage | PII scrubbing, quote validation, token/cost caps |

**Current scope:** Groww · Google Play Store · Google Docs MCP + Gmail MCP (external server).

## 2. System Context

```
Stakeholders ──► This Repository ──► External Services
                 ┌──────────────────────┐
                 │  Pulse CLI/Scheduler  │
                 │  Pulse Agent (MCP Host)│
                 │  ├─ Play Store Ingest │──► Google Play Store
                 │  ├─ Analysis Pipeline │──► Groq API (llama-3.3-70b-versatile)
                 │  ├─ Report & Email    │    OpenAI Embeddings API
                 │  │  Renderer          │
                 │  └─ Run Ledger        │
                 └──────────┬───────────┘
                            │ HTTP
                 ┌──────────▼───────────┐
                 │  External MCP Server  │──► Google Docs API
                 │  (mcp-server-saksham) │──► Gmail API
                 └──────────────────────┘
                            │
                 ┌──────────▼───────────┐
                 │  Google Doc (Groww)   │
                 │  Stakeholder Inboxes  │
                 └──────────────────────┘
```

The pulse agent orchestrates ingestion, analysis, rendering, and delivery. It connects to the external MCP server via HTTP. Google credentials and API access are confined to that server.

## 3. Logical Layers

| Layer | Responsibility | Must Not |
|-------|---------------|----------|
| Layer 1 — Data Retrieval | Fetch and normalize Play Store reviews for Groww | Call Google Workspace APIs |
| Layer 2 — Reasoning | Cluster, summarize, validate quotes | Write to Docs or Gmail |
| Layer 3 — Output Generation | Build structured Doc blocks and email HTML/text | Hold Google OAuth |
| Layer 4 — Delivery (MCP) | Append Doc section, send/draft email | Contain clustering/LLM logic |

## 4. Repository Layout

```
App-Review-Analyzer-main/
├── docs/
│   ├── problemStatement.md
│   ├── architecture.md
│   ├── implementation-plan.md
│   └── edge-cases.md
├── config/
│   ├── products/
│   │   └── groww.yaml          # Play Store app id, doc id, recipients
│   ├── pipeline.yaml           # window weeks, cluster params, LLM limits
│   └── mcp/                    # MCP config (env examples)
├── pulse/
│   ├── cli.py                  # Entry: run, backfill, dry-run
│   ├── agent/
│   │   └── mcp_client.py      # HTTP client for external MCP server
│   ├── ingestion/
│   │   ├── play_store.py       # Scraper + pagination
│   │   ├── normalizer.py       # Quality filters (words, language, emoji)
│   │   ├── cache.py            # reviews_raw / reviews_normalized cache
│   │   └── models.py           # Review, RawReview
│   ├── pipeline/
│   │   ├── scrubber.py         # PII redaction
│   │   ├── embeddings.py
│   │   ├── clustering.py       # UMAP + HDBSCAN
│   │   ├── summarizer.py       # LLM theme/quote/action generation
│   │   └── quote_validator.py  # Substring match against source reviews
│   ├── render/
│   │   ├── doc_section.py      # Plain-text blocks for Docs MCP
│   │   └── email_teaser.py     # HTML + plain text teaser
│   └── ledger/
│       └── store.py            # SQLite run ledger
├── data/                       # gitignored: cached reviews, run artifacts
└── .env.example
```

This layout keeps the MCP server external, the pulse pipeline local, and configuration separable.

## 5. End-to-End Run Flow

```
Pulse CLI
  │ run --product groww --iso-week 2026-W23
  ▼
Orchestrator (cli.py)
  ├── check idempotency (groww, 2026-W23) via Ledger
  │   ├─ already completed → skip (no-op success)
  │   └─ new or failed retry → continue
  ├── Ingestion: fetch_reviews(window=10w) → Review[]
  ├── Pipeline: analyze(reviews) → PulseReport (themes, quotes, actions)
  ├── Renderer: build_outputs(report, iso_week) → DocSection, EmailTeaser
  ├── MCP Client: POST /append_to_doc (doc_id, content)
  ├── MCP Client: POST /create_email_draft (to, subject, body)
  └── Ledger: record_run(metadata, delivery_ids) → success
```

### Run Inputs

| Parameter | Description | Example |
|-----------|-------------|---------|
| product | Product slug | `groww` |
| iso_week | ISO 8601 week | `2026-W23` |
| window_weeks | Rolling review window | `10` |
| dry_run | Skip MCP writes | `false` |
| mcp_server_url | URL of external MCP server | `http://localhost:8000` |

### Run Outputs (Audit Record)

```json
{
  "run_id": "groww-2026-W23-abc123",
  "product": "groww",
  "iso_week": "2026-W23",
  "review_count": 872,
  "window_weeks": 10,
  "started_at": "2026-06-08T03:30:00+05:30",
  "completed_at": "2026-06-08T03:42:11+05:30",
  "doc_delivery": {
    "document_id": "...",
    "section_anchor": "groww-2026-W23",
    "url": "https://docs.google.com/document/d/..."
  },
  "email_delivery": {
    "mode": "draft",
    "draft_id": "...",
    "idempotency_key": "groww-2026-W23-email"
  },
  "status": "completed"
}
```

## 6. Play Store Ingestion

### Responsibilities

1. Resolve Groww's Play Store listing from product config (`play_store.app_id`).
2. Scrape public reviews within the configured date window (8–12 weeks).
3. Paginate until window boundary or no more pages.
4. Normalize to a canonical `Review` model.

### Review Models

**Raw cache** (`reviews_raw.json`) — full scrape payload per review:

| Field | Type | Notes |
|-------|------|-------|
| text | string | Raw review body |
| rating | int | 1–5 stars |
| published_at | datetime | UTC; used for window filtering |

**Normalized pipeline input** (`reviews_normalized.json`) — what Phase 2 consumes:

| Field | Type | Notes |
|-------|------|-------|
| text | string | Review body passing quality filters |
| rating | int | 1–5 stars |

Phase 1 normalization: ≥8 words, English-only, no emoji. Typical Groww pull: ~800–900 normalized reviews from ~5,000 raw (~17% kept).

### Design Decisions

- Cache raw and normalized pulls under `data/cache/{product}/{date}/` to avoid re-scraping on retries.
- Deduplicate raw reviews by hash of `(text, rating, published_at)` before normalization.
- Rate limiting with backoff; ingestion failures abort the run before any Doc/email write.

## 7. Analysis Pipeline

**Input:** `list[Review]` with `{ text, rating }` from normalized cache or ingestion.

**ML floor:** If normalized review count < 20, abort before embedding.

### 7.1 PII Scrubbing

Run before embedding, LLM calls, and publishing.

| Pattern Class | Action |
|--------------|--------|
| Email addresses | Redact → `[EMAIL]` |
| Phone numbers (IN formats) | Redact → `[PHONE]` |
| Long numeric sequences (PAN/Aadhaar-like) | Redact → `[ID]` |
| URLs with tokens | Redact path/query |
| Financial amounts (10k, lakhs, $…) | Keep in v1 — useful theme signal |

### 7.2 Embeddings and Clustering

| Parameter | Default | Config Key |
|-----------|---------|------------|
| Embedding model | OpenAI / text-embedding-3-small | `pipeline.embedding.*` |
| UMAP n_neighbors | 15 | `pipeline.clustering.umap.n_neighbors` |
| UMAP n_components | 5 | `pipeline.clustering.umap.n_components` |
| UMAP random_state | 42 | `pipeline.clustering.umap.random_state` |
| HDBSCAN min_cluster_size | 5 | `pipeline.clustering.hdbscan.min_cluster_size` |
| Top clusters to summarize | 3–5 | `pipeline.summarization.max_themes` |
| Samples per cluster | 5–8 | `pipeline.summarization.max_samples_per_cluster` |

**Cluster ranking:** `score = cluster_size × (6 − avg_rating)` — prioritizes large low-star complaint themes.

Noise cluster (label = −1) reviews are excluded from theme generation.

### 7.3 LLM Summarization (Groq)

**Provider:** Groq — `llama-3.3-70b-versatile`.

**Call pattern:** One Groq request per top cluster. Sequential calls with rate limiting — no parallel LLM requests.

| Groq Limit | Value | Pipeline Implication |
|-----------|-------|---------------------|
| Requests/minute | 30 | ≥2s between requests |
| Requests/day | 1,000 | ~5 themes + ≤5 re-prompts ≈ 10 req/run |
| Tokens/minute | 12,000 | Pre-flight estimate per request < 10K tokens |
| Tokens/day | 100,000 | Cap `max_tokens_per_run` at 12,000 |

### 7.4 Quote Validation

Every Groq-produced quote must pass validation:

1. Normalize whitespace and punctuation on quote and candidate review texts.
2. Require case-insensitive substring match against at least one scrubbed review in the same cluster.
3. Accept ellipsis truncation as prefix match.
4. Quotes failing validation are dropped and logged; if a theme loses all quotes, re-prompt once or omit the theme.

## 8. Output Generation

### 8.1 Google Doc Section Structure

Each weekly run appends one section to *Weekly Review Pulse — Groww*:

```
Heading 1: Groww — Weekly Review Pulse — 2026-W23
  Paragraph: Period: Last 10 weeks (rolling) · Source: Google Play Store · Generated: 2026-06-08 IST
  Heading 2: Top Themes
    Bulleted list (theme name — summary)
  Heading 2: Real User Quotes
    Bulleted list (verbatim validated quotes)
  Heading 2: Action Ideas
    Bulleted list (title — detail)
  Heading 2: Who This Helps
    Short bullets (Product / Support / Leadership)
```

### 8.2 Section Anchor (Idempotency)

| Concept | Value |
|---------|-------|
| Anchor key | `{product}-{iso_week}` e.g. `groww-2026-W23` |
| Heading text | `Groww — Weekly Review Pulse — 2026-W23` |

### 8.3 Email Teaser

- **Subject:** `Groww Weekly Review Pulse — 2026-W23`
- **Body:** 3–5 bullet theme headlines + one-line context
- **CTA:** Read full report → deep link to Doc section
- **Footer:** generation timestamp, review window, link to full Doc

## 9. MCP Server Architecture

The project uses an **external MCP server** deployed separately ([mcp-server-saksham](https://github.com/saksham20189575/mcp-server-saksham)). The pulse agent communicates with it via HTTP:

| Endpoint | Method | Purpose | Key Inputs |
|----------|--------|---------|------------|
| `/append_to_doc` | POST | Append text to Google Doc | `doc_id`, `content` |
| `/create_email_draft` | POST | Create Gmail draft | `to`, `subject`, `body` |

The MCP server handles Google OAuth internally (credentials.json + token.json). The pulse agent never touches Google credentials.

## 10. Run Ledger and Audit

Central run ledger (SQLite) owned by the pulse agent, written after successful MCP delivery.

**Table: `runs`**

| Column | Description |
|--------|-------------|
| run_id | UUID |
| product | `groww` |
| iso_week | `2026-W23` |
| status | `pending`, `completed`, `failed` |
| review_count | int |
| window_weeks | int |
| started_at, completed_at | timestamps |
| error_message | nullable |

**Table: `deliveries`**

| Column | Description |
|--------|-------------|
| run_id | FK → runs |
| channel | `google_doc`, `gmail` |
| external_id | heading_id, message_id, draft_id |
| url | Doc or Gmail link |
| idempotency_key | nullable |

**Unique constraint:** `(product, iso_week)` on runs where `status = completed`.

## 11. Configuration

### Product Config — `config/products/groww.yaml`

```yaml
product: groww
display_name: Groww
play_store:
  app_id: com.nextbillion.groww
ingestion:
  window_weeks: 10
  min_reviews: 20
  max_reviews: 5000
  min_words: 8
  allowed_language: en
delivery:
  google_doc_id: "<SHARED_DOC_ID>"
  email:
    recipients:
      - product-leads@example.com
      - support-leads@example.com
    default_mode: draft
```

### Pipeline Config — `config/pipeline.yaml`

```yaml
embedding:
  provider: openai
  model: text-embedding-3-small
  batch_size: 64
clustering:
  umap:
    n_neighbors: 15
    n_components: 5
    metric: cosine
  hdbscan:
    min_cluster_size: 5
    min_samples: 3
summarization:
  provider: groq
  model: llama-3.3-70b-versatile
  max_themes: 5
  max_tokens_per_run: 12000
  max_samples_per_cluster: 8
  max_output_tokens_per_theme: 800
  request_interval_seconds: 2
safety:
  scrub_pii: true
  max_review_chars: 2000
```

## 12. CLI and Scheduling

### CLI Commands

| Command | Description |
|---------|-------------|
| `pulse run --product groww [--iso-week YYYY-Www]` | Run for current or specified ISO week |
| `pulse backfill --product groww --from 2026-W01 --to 2026-W20` | Sequential backfill with idempotency |
| `pulse dry-run --product groww` | Full pipeline except MCP writes |
| `pulse status --product groww --iso-week 2026-W23` | Show ledger + delivery ids |

### Scheduler

Cron / GitHub Actions / Cloud Scheduler invokes `pulse run --product groww` weekly (e.g. Monday 09:00 IST).

## 13. Security and Safety

| Risk | Mitigation |
|------|-----------|
| Google OAuth leakage | Credentials only in MCP server; gitignored |
| PII in reports | Scrubber before LLM and publish |
| Prompt injection via reviews | Data/non-instruction framing; no tool execution from review text |
| Hallucinated quotes | Substring validator against source reviews |
| Runaway LLM cost / Groq rate limits | max_tokens_per_run, per-cluster sample caps, sequential requests, 429 backoff |
| Duplicate stakeholder email | Idempotency key + ledger |
| Scraping abuse / blocks | Rate limits, retries, user-agent policy |

## 14. Error Handling and Partial Failure

| Failure Point | Behavior |
|--------------|----------|
| Ingestion fails | Abort; no Doc/email; ledger `failed` |
| Pipeline/LLM fails | Abort; no Doc/email; ledger `failed` |
| Doc append succeeds, Gmail fails | Ledger `failed` with partial delivery; retry safe |
| Gmail succeeds, ledger write fails | Log critical alert; idempotency still prevents duplicate |

Retries: orchestrator may retry transient errors with exponential backoff (max 3). Non-transient errors (auth, invalid doc id) fail fast.

## 15. Observability

| Signal | Mechanism |
|--------|-----------|
| Structured logs | JSON logs per stage with run_id, product, iso_week |
| Metrics | Review count, cluster count, Groq requests/tokens, embedding batch count, duration per stage |
| Artifacts | Optional JSON report snapshot in `data/runs/{run_id}/` |
| Audit queries | CLI `status` + SQL against ledger |

## 16. Environments

| Environment | Email Mode | Doc Target | Notes |
|------------|------------|------------|-------|
| Local dev | draft | Test Doc id | dry-run available |
| Staging | draft | Staging Doc | Requires explicit `--send` to override |
| Production | send | Production Doc | Scheduler default |

## 17. Testing Strategy

| Layer | Approach |
|-------|---------|
| Ingestion | Fixture HTML/JSON snapshots; no live scrape in unit tests |
| Scrubber / validator | Table-driven tests on synthetic PII and quotes |
| Clustering | Golden-file tests on fixed embedding inputs |
| Summarizer | Mock Groq client; schema validation; rate-limit retry tests |
| Docs/Gmail MCP | Contract tests with mocked endpoints |
| Orchestrator | Integration test: full run with MCP mocks + ledger idempotency |
| E2E (manual) | One dry-run and one draft email against real MCP server in staging |

## 18. Future Expansion (Out of Scope for v1)

| Extension | Touch Points |
|-----------|-------------|
| Additional products | New `config/products/*.yaml`; reuse pipeline + MCP |
| App Store RSS | New `ingestion/app_store.py` implementing ReviewSource |
| Multi-source merge | Fan-in before embed step; source dimension on Review |
| BI dashboard | Read from ledger + exported JSON; Doc remains canonical |

## 19. Architecture Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Delivery to Google | External MCP server | Isolates OAuth from pulse agent |
| Doc as source of truth | Append sections with anchors | History + idempotency |
| Email content | Teaser + deep link | Avoid duplicate maintenance |
| Clustering | UMAP + HDBSCAN | Unsupervised theme discovery |
| Cluster ranking | `size × (6 − avg_rating)` | Surfaces actionable low-star themes |
| Summarization LLM | Groq llama-3.3-70b-versatile | Cost-effective; respects 12K TPM |
| Embeddings | OpenAI text-embedding-3-small | Batch-friendly for ~800+ reviews |
| Quote trust | Post-LLM substring validation | Prevents fabricated user voice |
| Idempotency | Anchor + email key + ledger | Safe weekly cron and backfill |
| v1 scope | Groww Play Store only | Reduce ingestion and config surface |

## 20. Related Documents

- [problemStatement.md](problemStatement.md) — product intent, requirements, and non-goals
- [implementation-plan.md](implementation-plan.md) — phase-wise build plan and exit criteria
- [edge-cases.md](edge-cases.md) — clustering fallbacks, quote validation, and failure modes
