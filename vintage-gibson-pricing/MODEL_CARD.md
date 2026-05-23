# Model card — gibson-price

## Intended use

A research/demo predictor of secondary-market prices for vintage acoustic guitars,
weighted toward Gibson flat-tops (J-45, SJ-200, Hummingbird, Dove, Southern Jumbo,
L-00, LG-2, J-160E, Advanced Jumbo, Nick Lucas), with Martin / Guild / Gretsch
included as brand comparators.

**Inputs**: brand, model family, year of manufacture, 7-point condition grade,
originality flags (refinish / headstock break / neck reset / refret / replaced
tuners / replaced bridge / cracks), provenance flags (original case / receipt /
pre-war certification / famous prior owner), and a few tonewood/finish overrides.

**Outputs**: median predicted price in USD, a calibrated 80% prediction interval,
SHAP-based top contributors, a natural-language summary, and the nearest
comparable sales from the seed dataset.

## Out-of-scope use

> **Do not use for insurance valuation, sale negotiation, lending collateral
> appraisal, or any consequential financial decision.**

This is a portfolio demonstration trained on a small seed dataset. Vintage guitar
valuation requires physical inspection by a qualified appraiser. The model's
80% intervals are wide for good reason — single-instrument variation,
provenance, and condition nuance dominate the residual.

## Training data

| Source | Role | Notes |
| --- | --- | --- |
| Vintage Guitar Price Guide seed CSV (`data/seed/gibson_acoustic_seed.csv`) | Primary calibration | Expanded from `price_ranges.yaml`, anchored on published price-guide bands, Gruhn's Guide, Joe's Vintage Guitars and Carter Vintage public comps, Heritage Auctions realised prices, Reverb Price Guide public ranges. |
| Reverb API (`reverb_api.py`) | Active listings (asking prices) | Requires `REVERB_API_TOKEN`. Asking-price ≠ sold-price; the `source` feature lets the model learn the discount. |
| Heritage Auctions archive (`heritage_scraper.py`) | Premium-tier realised prices | Public auction-archive scrape with robots.txt respect and 2.5s rate limit. |
| Wayback-Machine dealer snapshots (`dealer_archive.py`) | Gruhn / Carter Vintage / Elderly / Folkway | Snapshot diff to infer sold items. Per-dealer parsers are skeletons. |
| Reverb Price Guide scrape (`reverb_scraper.py`) | Optional, env-gated | **DISABLED unless `REVERB_SCRAPER_ENABLED=1` is set.** The Reverb Price Guide is a paid product; their Terms of Service prohibit scraping. Gated for personal research use only. |

The seed CSV is the only source committed to the repo; all live-pull sources
write to `data/raw/` which is gitignored.

## Known biases

- **Reverb (active)** skews toward modern USA-made and store-grade examples.
  Asking prices on Reverb are typically 5–15% above realised sold prices; the
  model's `source` categorical lets it learn this offset.
- **Heritage Auctions** skews to the high-end / premium tier (pre-war D-45s,
  banner J-45s, museum-grade examples). Under-represented for mid-market 1970s
  guitars.
- **VG Price Guide ranges** are dealer-consensus bands updated annually, which
  lag real-time market movements (e.g., the 2020-22 COVID-era spike) by ~12-18 months.
- **Dealer snapshots** (when wired up) skew to clean, well-described examples —
  dealers select the inventory they choose to list.
- **Model-family imbalance**: J-45 / D-28 are over-represented vs LG-2 /
  Nick Lucas. The hierarchical residual model applies empirical-Bayes
  shrinkage to compensate, but per-family MAPE for sparse families is higher.
- **Geographic**: prices reflect the US market. UK / EU / JP markets diverge
  materially (Brazilian rosewood CITES restrictions affect intercontinental sales).
- **Currency**: all prices in USD.

## Modeling approach

1. **Base regressor**: LightGBM on `log(price)` with native categorical handling.
   Forward-chaining time split (oldest 70% / middle 15% calibration / newest 15%
   holdout) — *not* random k-fold, to avoid leaking the 2020-22 regime shift.
2. **Prediction intervals**: Conformalized Quantile Regression (CQR;
   Romano, Patterson, Candès 2019) on the calibration set, producing 80%
   intervals with finite-sample coverage guarantees.
3. **Hierarchical residual model**: empirical-Bayes shrinkage on log-residuals
   by `(model_family × era_segment)`. Adjusts for the LightGBM under-reaction
   on sparse model families.
4. **Bias correction**: Duan-smearing on the log → dollar back-transform using
   training-set residuals.
5. **Explanations**: SHAP TreeExplainer applied per row; values are translated
   from log-scale to dollar contributions for display.

## Failure modes

- Out-of-distribution model families (e.g., a rare specialty model not in the
  seed CSV) fall back to brand-mean behaviour. The Streamlit app indicates this
  via the `confidence: low` label and a wide interval.
- Famous-prior-owner premiums are capped in the synthetic augmentation rules
  at 1.5×. Real provenance can multiply price by 5-50× (e.g., Bob Dylan's 1964
  Gibson). The model will systematically under-price these — accept the
  miss; it would take a celebrity-detection feature to handle it.
- Refinish detection from listing-text regex has high recall but moderate
  precision. False positives slightly under-price; false negatives badly
  over-price. Manually setting the `refinished` flag in the UI is more reliable
  than trusting auto-parsing.

## Reproducibility

Each trained artifact embeds a `data_sha` field (SHA-256 prefix of the input
feature frame). To reproduce a prediction, restore the same seed CSV and pull
the matching artifact bundle. The eval report (`reports/eval.html`) is
regenerated on every train run and a snapshot is committed.

## Disclaimers

This work is independent research and is not affiliated with Gibson Brands,
Inc., Reverb LLC, Heritage Auctions, Vintage Guitar Magazine, or any dealer.
All trademarks are the property of their respective owners.
