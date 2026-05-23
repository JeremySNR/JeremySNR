"""Smoke tests for the modeling layer — verifies wiring without requiring much data."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gibson_price.models.conformal import empirical_coverage, fit_cqr
from gibson_price.models.gbm import predict_log, train_gbm
from gibson_price.models.hierarchical import fit_hierarchical
from gibson_price.schema import ALL_FEATURES


def _toy_frame(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    models = ["J-45", "J-200", "Hummingbird", "D-28"]
    brands = ["Gibson", "Gibson", "Gibson", "Martin"]
    for _ in range(n):
        idx = rng.integers(0, 4)
        year = int(rng.integers(1940, 2020))
        condition = int(rng.integers(3, 8))
        refin = int(rng.random() < 0.2)
        base_log = 8 + (1940 - year) * -0.01 + condition * 0.15 - refin * 0.4
        price = float(np.exp(base_log + rng.normal(0, 0.2)))
        row = {f: 0 for f in ALL_FEATURES}
        row["brand"] = brands[idx]
        row["model_family"] = models[idx]
        row["year"] = year
        row["era_segment"] = "golden" if 1942 <= year < 1965 else "transition"
        row["factory"] = "Kalamazoo"
        row["body_shape"] = "Dreadnought"
        row["top_wood"] = "Sitka"
        row["back_sides_wood"] = "Mahogany"
        row["bracing_pattern"] = "X-brace"
        row["bridge_type"] = "Rosewood Pin"
        row["tuner_type"] = "Kluson Single-Line"
        row["finish"] = "Sunburst"
        row["sunburst_pattern"] = "Tobacco"
        row["source"] = "vg_guide"
        row["condition_grade"] = condition
        row["refinished"] = refin
        row["sold_year"] = 2024
        row["price_usd"] = price
        rows.append(row)
    return pd.DataFrame(rows)


def test_gbm_trains_and_predicts() -> None:
    df = _toy_frame(300)
    y_log = np.log(df["price_usd"].to_numpy())
    model = train_gbm(df, y_log)
    preds = predict_log(model, df)
    assert preds.shape == (300,)
    assert np.isfinite(preds).all()


def test_cqr_intervals_are_ordered() -> None:
    df = _toy_frame(400)
    train, calib, test = df.iloc[:250], df.iloc[250:325], df.iloc[325:]
    y_train_log = np.log(train["price_usd"].to_numpy())
    y_calib_log = np.log(calib["price_usd"].to_numpy())
    y_test_log = np.log(test["price_usd"].to_numpy())

    cqr = fit_cqr(train, y_train_log, calib, y_calib_log, alpha=0.2)
    lo, hi = cqr.predict_interval(test)
    assert (lo <= hi).all(), "lower bound must not exceed upper bound"

    coverage = empirical_coverage(cqr, test, y_test_log)
    assert 0.55 <= coverage <= 1.0, f"coverage {coverage:.2f} wildly off target"


def test_hierarchical_returns_per_group_means() -> None:
    df = _toy_frame(200)
    residuals = np.random.default_rng(1).normal(0, 0.1, size=len(df))
    hier = fit_hierarchical(df, residuals)
    preds = hier.predict(df)
    assert preds.shape == (len(df),)
    assert np.isfinite(preds).all()
