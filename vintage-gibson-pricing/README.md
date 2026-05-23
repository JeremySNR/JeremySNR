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
│   └── ingest.py              # pull from a chosen live source
├── notebooks/                 # EDA + SHAP analysis
├── tests/                     # serial dating, feature engineering, model smoke tests
├── reports/eval.html          # auto-generated calibration / per-family MAPE report
├── MODEL_CARD.md              # data provenance, biases, intended use, disclaimers
└── Dockerfile                 # for Streamlit Cloud / Hugging Face Spaces
```

## Data sources

| Source | Type | Notes |
| --- | --- | --- |
| Seed CSV (`vg_guide`) | Calibration anchor (committed) | Expanded from `price_ranges.yaml`, anchored on Vintage Guitar Price Guide, Gruhn's Guide, Joe's Vintage / Carter Vintage public comps, Heritage realised prices |
| Reverb API | Active asking prices | Requires `REVERB_API_TOKEN` |
| Heritage Auctions archive | Realised auction prices (premium tier) | Public crawl with robots.txt respect |
| Dealer archive (Wayback) | Gruhn / Carter / Elderly / Folkway snapshots | Sold-state inferred via snapshot diff |
| Reverb Price Guide scrape | **Disabled by default** | Reverb ToS prohibits scraping; gated behind `REVERB_SCRAPER_ENABLED=1`, personal research use only |

See [`MODEL_CARD.md`](MODEL_CARD.md) for known biases and full provenance.

## What it is **not**

Not an appraisal tool. Not for insurance, lending, sale negotiation, or any
consequential decision. The seed dataset is ~800 rows; the model's 80%
intervals are wide for good reason. Real appraisal requires physical
inspection by a qualified expert.

## License

MIT.
