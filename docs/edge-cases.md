# Weekly Product Review Pulse — Edge Cases

This document covers clustering fallbacks, quote validation edge cases, and failure modes referenced by the architecture.

---

## 1. Ingestion Edge Cases

### 1.1 Insufficient Reviews
- **Condition:** Fewer than `min_reviews` (20) normalized reviews after filtering.
- **Behavior:** Abort the run before embedding. Ledger status: `failed`, error: "Insufficient reviews."
- **Rationale:** Clustering on <20 data points produces unreliable themes.

### 1.2 All Reviews Filtered Out
- **Condition:** Normalization removes 100% of raw reviews (e.g., all are <8 words or non-English).
- **Behavior:** Same as 1.1 — abort with a descriptive error.

### 1.3 Scraper Returns Empty
- **Condition:** Google Play scraper returns 0 reviews (app delisted, network error, rate-limited).
- **Behavior:** Abort immediately. Log the scraper error. Ledger `failed`.

### 1.4 Duplicate Reviews Across Windows
- **Condition:** Re-scraping overlapping time windows produces duplicate reviews.
- **Behavior:** Deduplicate by hash of `(text, rating, published_at)` before normalization. Reviews with identical content but different metadata are still treated as duplicates.

---

## 2. PII Scrubbing Edge Cases

### 2.1 False Positives
- **Condition:** A financial amount like "₹10,000" or an app version like "4.5.12.3456" matches the PII regex.
- **Behavior:** Financial amounts are kept (useful theme signal). Version numbers: the Aadhaar regex (`\b\d{12}\b`) only matches exactly 12-digit sequences, so shorter version strings are not affected.

### 2.2 PII in Non-English Text
- **Condition:** Phone numbers or IDs in Hinglish or regional scripts.
- **Behavior:** The regex-based scrubber handles digit patterns regardless of language. Names in non-Latin scripts are not scrubbed (out of v1 scope—normalization drops non-English reviews anyway).

### 2.3 URLs with Tokens
- **Condition:** Reviews containing tracking URLs with session tokens.
- **Behavior:** Current scrubber does not handle URLs. This is a known gap for v1. If needed, add `re.sub(r'https?://\S+', '[URL]', text)`.

---

## 3. Clustering Fallbacks

### 3.1 All Reviews Assigned to Noise (label = −1)
- **Condition:** HDBSCAN finds no dense clusters; every review is noise.
- **Fallback:**
  1. Lower `min_cluster_size` by half (e.g., 5 → 3) and re-cluster once.
  2. If still all noise, abort and log: "No meaningful clusters found."
- **Rationale:** Forcing clusters on uniformly distributed data produces misleading themes.

### 3.2 One Dominant Cluster (>80% of Reviews)
- **Condition:** A single cluster absorbs most reviews.
- **Fallback:**
  1. Optionally split by rating bucket (1–2★ vs 4–5★) and re-rank sub-clusters.
  2. If not split, treat as a single broad theme. The LLM may still produce useful sub-insights from the sampled reviews.
- **Rationale:** A mega-cluster is often "general satisfaction/dissatisfaction" — splitting by rating reveals more specific themes.

### 3.3 Many Micro-Clusters (<3 reviews each)
- **Condition:** Dozens of tiny clusters, none with meaningful size.
- **Fallback:** Take the top `max_themes` (5) by score (`size × (6 − avg_rating)`) only. Tiny clusters will naturally score low and be excluded.

### 3.4 UMAP Failure
- **Condition:** UMAP raises an error (e.g., too few samples for `n_neighbors=15`).
- **Fallback:**
  1. If `n_samples < n_neighbors`, reduce `n_neighbors` to `n_samples − 1`.
  2. If `n_samples < n_components`, reduce `n_components` to `n_samples − 1`.
  3. If still failing, abort.

---

## 4. Quote Validation Edge Cases

### 4.1 LLM Paraphrases Instead of Quoting
- **Condition:** The LLM produces a "quote" that summarizes rather than reproducing verbatim text.
- **Behavior:** Fails substring validation → dropped. Logged as "hallucinated quote."
- **Mitigation:** The prompt explicitly instructs "exact verbatim quote from the reviews."

### 4.2 Ellipsis Truncation
- **Condition:** The LLM shortens a long quote using `...` or `…` (e.g., "The app freezes exactly when the market opens...").
- **Behavior:** Strip trailing ellipsis before validation; check if the remainder is a prefix substring of any source review.

### 4.3 Whitespace / Punctuation Variations
- **Condition:** Minor differences in whitespace, dashes, or punctuation between the LLM quote and the source.
- **Behavior:** The `clean_text()` normalizer strips punctuation and collapses whitespace before comparison. This handles most variations.

### 4.4 Hinglish / Mixed-Language Quotes
- **Condition:** Reviews contain Romanized Hindi mixed with English.
- **Behavior:** Case-insensitive match only. No translation or transliteration is attempted. If the LLM translates a Hinglish review, the quote fails validation (by design — we want verbatim).

### 4.5 All Quotes Fail for a Theme
- **Condition:** Every quote in a theme's output fails validation.
- **Behavior:**
  1. Re-prompt the LLM once for that cluster (counts toward RPM/RPD budget).
  2. If the re-prompt's quotes also fail, omit the theme entirely from the report.
  3. Log the omitted theme for debugging.

### 4.6 Quote Appears in a Different Cluster
- **Condition:** The LLM produces a valid quote, but it belongs to a review in a different cluster.
- **Behavior:** Primary validation checks the same cluster's reviews. If no match, fallback checks the full scrubbed corpus. If found in the corpus, the quote is accepted (the review may have been borderline between clusters).

---

## 5. LLM / Groq Failure Modes

### 5.1 Rate Limit (HTTP 429 / 529)
- **Condition:** Groq returns 429 (rate limit) or 529 (overloaded).
- **Behavior:** Exponential backoff with jitter (initial wait: 2s, max retries: 3). If exhausted, abort the run.

### 5.2 Invalid JSON Response
- **Condition:** The LLM returns malformed JSON or a response that doesn't match the expected schema.
- **Behavior:** Strip markdown fences (```` ```json ... ``` ````), retry parse. If still invalid, re-prompt once. If still invalid, skip the theme.

### 5.3 Token Budget Exceeded
- **Condition:** Cumulative tokens across all cluster requests exceed `max_tokens_per_run` (12,000).
- **Behavior:** Pre-flight estimate before each request. If over budget, drop the longest sample reviews first. If still over, skip remaining clusters.

### 5.4 Empty or Nonsensical Output
- **Condition:** The LLM returns an empty `theme_name` or an obviously generic response.
- **Behavior:** Schema validation checks for non-empty `theme_name` and `summary`. If invalid, re-prompt once or skip.

---

## 6. MCP Delivery Failure Modes

### 6.1 MCP Server Unreachable
- **Condition:** The external MCP server is down or the URL is wrong.
- **Behavior:** HTTP connection error → abort delivery, ledger `failed`. The pipeline output (themes, report) is still logged locally for retry.

### 6.2 Google Doc Append Fails
- **Condition:** Invalid `doc_id`, expired OAuth token, or permissions issue on the MCP server side.
- **Behavior:** MCP server returns error → abort delivery, ledger `failed`. No email is sent (Doc is prerequisite for the deep link).

### 6.3 Gmail Draft Fails After Doc Succeeds
- **Condition:** Doc append succeeds but Gmail draft creation fails.
- **Behavior:** Ledger records partial delivery (`google_doc` channel only), status `failed`. On retry, the Doc append is safe (idempotent — the MCP server should not duplicate the section), and Gmail is retried.

### 6.4 Duplicate Prevention
- **Condition:** Retry after a partially successful run.
- **Behavior:**
  - **Ledger level:** Unique constraint `(product, iso_week)` where `status = completed` prevents marking a duplicate run as complete.
  - **MCP level:** The MCP server's Doc append should check for existing section headings. The email idempotency key (`{product}-{iso_week}-email`) prevents duplicate drafts.

---

## 7. Ledger / Persistence Edge Cases

### 7.1 Concurrent Runs for Same Product+Week
- **Condition:** Two CLI invocations run simultaneously for `groww` + `2026-W23`.
- **Behavior:** The first to call `ledger.start_run()` succeeds. The second will either:
  - Hit the unique constraint on completed runs, or
  - Both start as `pending`, but only one can be marked `completed` (constraint).
- **Mitigation:** For v1, sequential execution is assumed (cron-based). True concurrency requires advisory locks.

### 7.2 Ledger Database Corruption
- **Condition:** SQLite file is corrupted or deleted.
- **Behavior:** `_init_db()` recreates tables on next run. Historical data is lost, but runs are safe — the MCP server's own idempotency (Doc heading check, email key) prevents duplicates even without the ledger.

### 7.3 Disk Full
- **Condition:** Cannot write to SQLite or cache files.
- **Behavior:** Python `IOError` → caught by the outer `try/except` in `cli.py`, logged, run marked as `failed` (if the ledger itself is writable). If even the error recording fails, stderr output is the last resort.
