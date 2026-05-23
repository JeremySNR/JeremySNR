# Dealer / data-source policy

This project ingests vintage guitar pricing data from several public sources.
This file documents what each source allows, how the project respects it,
and how to request removal.

## Principles

1. **Public data only**. We never pull behind paywalls, logins, or
   subscription-gated APIs.
2. **Respect robots.txt** on every host. `ingest/base.py:polite_get` enforces this.
3. **Rate limit** every host to ≤1 request per 2 seconds (most sources use 2.5–3s).
4. **Identify ourselves**. The `User-Agent` header reads
   `gibson-price-research/0.1 (+https://github.com/JeremySNR/JeremySNR; personal research)`
   so dealers can identify our traffic and contact the project owner.
5. **Cache aggressively**. Every fetch is cached for 12 hours to 90 days
   depending on source — if we already have a snapshot, we don't refetch.
6. **No re-distribution**. We never publish the raw scraped data — only model
   predictions derived from it.

## Source-by-source

| Source | Access mode | ToS / robots position | How we comply |
| --- | --- | --- | --- |
| **Reverb API** (`reverb_api.py`) | Authenticated OAuth | Official documented API | Use bearer-token auth; respect rate-limit headers |
| **Reverb Price Guide scrape** (`reverb_scraper.py`) | HTML scrape | **ToS prohibits scraping** | **DISABLED by default**. Module raises on import unless `REVERB_SCRAPER_ENABLED=1`. Gated for personal research only. Will be removed entirely on request from Reverb. |
| **Shopify storefront `/products.json`** (`dealers/shopify.py`) | Public JSON endpoint | Standard Shopify interoperability surface; same data as anonymous browser | robots-check + 2s rate limit + on-disk cache. Degrades gracefully on 401/403/404 (treat as opted-out). |
| **Heritage Auctions archive** (`heritage_scraper.py`) | HTML scrape of public archive | Public auction results; site allows search-engine crawling | robots-check + 2.5s rate limit + 30-day cache |
| **Wayback Machine CDX** (`wayback.py`) | Public archive API | Internet Archive welcomes programmatic access | 1.5s rate limit + 90-day cache |
| **Vintage Guitar Price Guide** (`vg_price_guide.py`) | Manual transcription of published values | Quoting price-guide ranges is fair use for research | No automated fetching; the seed CSV is hand-curated from the published guide and dealer comps |
| **Custom dealer parsers** (`dealers/custom/*`) | HTML scrape | Each dealer's robots.txt and ToS apply | robots-check + 2.5–3s rate limit + 7-day cache. Skip if blocked. |

## Request removal

If you operate a dealer site indexed by this project and prefer not to be
included, open an issue at https://github.com/JeremySNR/JeremySNR/issues
or email the project owner (see profile). We will:

1. Add an `enabled=False` flag for your dealer in
   `src/gibson_price/ingest/dealers/registry.py`.
2. Remove cached data for your host.
3. Delete the corresponding extractor module if you prefer.

This is a research project, not a commercial scraping operation. Compliance
is by design.

## Live-pull defaults

When run from a public CI environment (e.g. GitHub Actions for the demo
Streamlit deploy), the orchestrator (`scripts/run_all_ingest.py`) only runs
against the Vintage Guitar Price Guide seed CSV and Reverb API. All HTML
scrapers and the Wayback diff require explicit opt-in via local run.

The committed `reports/eval.html` was generated from the seed CSV alone —
no live-pulled data has been published.
