# gibson-price

> Vintage acoustic guitar pricing predictor, focused on Gibson. Hedonic gradient
> boosting with calibrated 80% prediction intervals, empirical-Bayes hierarchical
> shrinkage by model family, and SHAP-based explanations.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Status](https://img.shields.io/badge/status-portfolio--demo-orange)

---

## What this is

A research-grade price predictor for vintage acoustic guitars. You pick a
brand, model, year, condition, and originality / provenance flags; the model
returns a median dollar value, a calibrated 80% prediction interval, the top
SHAP contributors, and the nearest comparable sales from a seed dataset.

Gibson acoustic flat-tops are the primary focus (J-45, SJ-200, Hummingbird,
Dove, Southern Jumbo, L-00, LG-2, J-160E, Advanced Jumbo, Nick Lucas). Martin,
Guild, and Gretsch are included as brand comparators so the model learns
brand-relative pricing.

## Why it's interesting (modeling)

Vintage guitar pricing is a textbook hedonic problem with three properties
that make naive approaches fall over:

1. **Extreme heteroscedasticity** — a 1942 J-45 ranges roughly $5k–$50k purely
   on originality. → CQR for calibrated intervals instead of point estimates.
2. **Strong domain rules** the model can leverage — the *1955 scalloped-bracing
   cliff*, the *1961–69 adjustable-bridge era* (material price deduction), the
   *Kalamazoo→Bozeman 1984/1989 factory shift*, the *Brazilian→Indian rosewood
   1969 CITES inflection*. → encoded as features; not left to discovery.
3. **Class imbalance** across model families (J-45 plentiful, LG-2 sparse). →
   empirical-Bayes residual shrinkage by `(model_family × era_segment)` so
   sparse families partial-pool toward their era cohort rather than the global
   mean.

The full stack:

| Layer | What | Why |
| --- | --- | --- |
| Base | **LightGBM** on `log(price)` with native categorical handling | Sub-second training, strong baseline on tabular hedonic data |
| Intervals | **Conformalized Quantile Regression** (Romano et al. 2019) | Finite-sample 80% coverage guarantee under exchangeability |
| Shrinkage | **Empirical-Bayes residual model** per `(model_family × era)` | Handles sparse model families without a slow MCMC sampler |
| Bias | **Duan-smearing** back-transform from log to USD | Avoids the systematic underestimate from naive `exp()` |
| Explain | **SHAP TreeExplainer** rescaled to USD contributions | One sentence + a table per prediction |
| Split | **Forward-chaining time CV** (oldest train, newest holdout) | The 2020–22 COVID spike makes random k-fold leaky |
| Compound mods | Structural-alteration features (top_replaced, neck_replaced, rebraced, frankenguitar...) + era-distance | Captures "what if a 40s guitar was retopped in the 60s" — period-correct vs modern-repro replacements get distinct deductions |
| Market index | **Hedonic Case-Shiller-style index** (per brand × model_family, quarterly) | Decomposes prices into stable feature effects + time effects; the time series is what we forecast |
| Forecast | **Ridge regression on the index** with optional FRED macro regressors (SP500, DGS10, CPI, M2) + adaptive conformal bands | Honest about data limits — refuses to forecast when <8 periods of history |

## Quickstart

```bash
# Install
pip install -e ".[app]"

# Build the seed CSV (~800 rows from data/seed/price_ranges.yaml)
python scripts/build_seed.py

# Train (writes artifacts/model.pkl + reports/eval.html)
python scripts/train.py

# Tests
pytest

# Run the Streamlit demo
streamlit run app/streamlit_app.py
```

## Project layout

```
gibson-price/
├── src/gibson_price/
│   ├── schema.py              # pydantic GuitarListing / FeatureRow / PricePrediction
│   ├── ingest/                # 5 sources: vg_guide (seed), reverb_api, heritage, dealer_archive, reverb_scrape (gated)
│   ├── features/              # serial dating, condition normalize, originality regex, tonewood, build
│   └── models/                # gbm, conformal (CQR), hierarchical (EB shrinkage), explainer, train, predict, comps
├── app/streamlit_app.py       # web demo
├── data/seed/
│   ├── price_ranges.yaml      # range specs anchored on published VG Price Guide bands
│   └── gibson_acoustic_seed.csv  # generated from price_ranges.yaml
├── scripts/
│   ├── build_seed.py          # generates the seed CSV
│   ├── train.py               # train + eval report
│   ├── ingest.py              # pull from a single chosen live source
│   └── run_all_ingest.py      # orchestrator: every dealer + Heritage + Wayback diff
├── notebooks/                 # EDA + SHAP analysis
├── tests/                     # 39 tests: serial dating, features, title parsing, wayback diff, model
├── reports/eval.html          # auto-generated calibration / per-family MAPE report
├── MODEL_CARD.md              # data provenance, biases, intended use, disclaimers
├── DEALER_POLICY.md           # per-source ToS posture + opt-out instructions
└── Dockerfile                 # for Streamlit Cloud / Hugging Face Spaces
```

## Data sources

The ingest layer is built around a single dealer registry
(`src/gibson_price/ingest/dealers/registry.py`). Adding a Shopify-based
dealer is one line; adding a custom-CMS dealer is one ~60-line file plus
one registry entry.

### Live-pull sources (each writes JSONL + manifest to `data/raw/`)

**23 dealers** in the registry, dispatched by `platform`:

| Platform | Strategy | Code path | Dealers |
| --- | --- | --- | --- |
| `shopify` | Public `/products.json` endpoint (no scraping needed) | `dealers.shopify.fetch_products` | Carter Vintage, Norman's Rare, Emerald City, Imperial Vintage, Wildwood, Dream, Retrofret, Lark Street |
| `generic` | **sitemap.xml + JSON-LD** — adding a dealer = one line in the registry | `dealers.generic.fetch_via_sitemap_jsonld` | Mass Street, The Twelfth Fret, TR Crandall, Folkway, Vintage Instruments (Philly), Acoustic Vibes, Mahar's, Joe's Vintage, True Vintage Guitar, Edgewater, CME Vintage |
| `custom` | Bespoke parser for sites that don't expose JSON-LD | `dealers.custom.*` | Gruhn, Elderly, The Music Emporium, Vintage And Rare (aggregator) |

Plus four cross-cutting sources:

| Source | Module | Mode | Notes |
| --- | --- | --- | --- |
| **Heritage Auctions** | `heritage_scraper` | HTML scrape of public archive | Realised premium-tier auction prices |
| **Reverb API** | `reverb_api` | Official OAuth API | Active listings (asking prices); requires `REVERB_API_TOKEN` |
| **Wayback Machine** | `dealer_archive` + `wayback` | CDX timemap + snapshot diff | Infers sold items: present in T1, gone for ≥2 consecutive snapshots ⇒ `price_confidence="inferred"` |
| **Common Crawl** | `common_crawl` + `dealers.generic.fetch_via_common_crawl` | CDX URL Index + WARC byte-range S3 fetch | **Historical backfill across every dealer with `common_crawl_domain` set.** 10+ years of snapshots, free, no site contact — the single biggest unlock for "every guitar ever sold online" |
| **Reverb Price Guide scrape** | `reverb_scraper` | **Disabled by default** | Reverb ToS prohibits scraping; gated behind `REVERB_SCRAPER_ENABLED=1` |

### Committed calibration anchor

| Source | Module | Notes |
| --- | --- | --- |
| **Vintage Guitar Price Guide seed CSV** | `vg_price_guide` | 684 rows hand-curated from published VG Price Guide bands, Gruhn's Guide, Joe's Vintage / Carter Vintage public comps, Heritage realised prices |

See [`MODEL_CARD.md`](MODEL_CARD.md) for known biases and [`DEALER_POLICY.md`](DEALER_POLICY.md) for the per-source ToS posture and opt-out process.

### Running the orchestrator

```bash
# Pull from every enabled source (writes data/raw/<source>.jsonl + .manifest.json)
python scripts/run_all_ingest.py

# Just one or two sources
python scripts/run_all_ingest.py --only carter_vintage,gruhn

# Skip the slow steps
python scripts/run_all_ingest.py --skip-wayback --skip-heritage

# Historical-only run: don't touch live dealer sites, only pull Common Crawl
python scripts/run_all_ingest.py --common-crawl-only
```

Each source writes a manifest with timing, count, and errors — `cat data/raw/*.manifest.json` shows source health without re-running. Sources degrade gracefully on robots.txt block or HTTP errors (manifest captures the error, run continues).

## What it is **not**

Not an appraisal tool. Not for insurance, lending, sale negotiation, or any
consequential decision. The seed dataset is ~800 rows; the model's 80%
intervals are wide for good reason. Real appraisal requires physical
inspection by a qualified expert.

## License

MIT.
