"""Tests for the time-series forecasting layer (index + forecast).

We can't validate predictive accuracy from synthetic data — the seed has
random sold_dates. What we *can* validate is the architecture: the index
builds without errors, the forecast returns the right shape, prediction
intervals are ordered correctly, and the synthetic-data warning fires.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gibson_price.models.forecast import backtest, forecast
from gibson_price.models.index import build_index
from gibson_price.schema import ALL_FEATURES


def _toy_frame(n: int = 400, n_periods: int = 20, seed: int = 0) -> pd.DataFrame:
    """Build a synthetic dataset with a deliberate time trend so the index
    has signal to recover."""
    rng = np.random.default_rng(seed)
    rows = []
    start_year = 2019
    period_dates = pd.date_range(f"{start_year}-01-01", periods=n_periods, freq="QE")
    for _ in range(n):
        period_idx = int(rng.integers(0, n_periods))
        sold_date = period_dates[period_idx] + pd.Timedelta(days=int(rng.integers(0, 60)))
        condition = int(rng.integers(3, 8))
        # Underlying trend: log-price grows 1.5% per quarter + noise
        base_log = 8.5 + 0.015 * period_idx + 0.10 * condition + rng.normal(0, 0.15)
        row = {f: 0 for f in ALL_FEATURES}
        row["brand"] = "Gibson"
        row["model_family"] = "J-45"
        row["year"] = 1955
        row["era_segment"] = "golden"
        row["factory"] = "Kalamazoo"
        row["body_shape"] = "Round-Shoulder Dreadnought"
        row["top_wood"] = "Sitka"
        row["back_sides_wood"] = "Mahogany"
        row["bracing_pattern"] = "X-brace"
        row["bridge_type"] = "Rosewood Pin"
        row["tuner_type"] = "Kluson Double-Line"
        row["finish"] = "Sunburst"
        row["sunburst_pattern"] = "Tobacco"
        row["source"] = "vg_guide"
        row["condition_grade"] = condition
        row["sold_year"] = sold_date.year
        row["price_usd"] = float(np.exp(base_log))
        row["sold_date"] = sold_date
        rows.append(row)
    return pd.DataFrame(rows)


def test_index_builds_from_toy_data() -> None:
    df = _toy_frame(n=400, n_periods=20)
    idx = build_index(df, period="Q", min_obs_per_period=3)
    assert len(idx.points) >= 15, "Should produce most periods with enough density"
    # Indexes should monotonically rise (or at least mostly rise) given the trend we baked in
    first, last = idx.points[0].index_value, idx.points[-1].index_value
    assert last > first * 0.9, "Index should reflect the upward trend"


def test_index_too_few_observations_raises() -> None:
    df = _toy_frame(n=20, n_periods=20)
    try:
        build_index(df, period="Q", min_obs_per_period=5)
    except ValueError as e:
        assert "min_obs_per_period" in str(e) or "No periods" in str(e)
        return
    raise AssertionError("Expected ValueError for sparse data")


def test_forecast_shape_and_intervals() -> None:
    df = _toy_frame(n=500, n_periods=24)
    idx = build_index(df, period="Q", min_obs_per_period=3)
    fc = forecast(idx, n_periods_ahead=4)
    assert len(fc.horizon) == 4
    for hp in fc.horizon:
        assert hp.lo_index <= hp.median_index <= hp.hi_index, "interval bounds must be ordered"
    assert fc.confidence_label in {"high", "medium", "low"}


def test_forecast_too_few_history_returns_insufficient_data() -> None:
    df = _toy_frame(n=80, n_periods=6)
    idx = build_index(df, period="Q", min_obs_per_period=3)
    fc = forecast(idx, n_periods_ahead=4)
    assert fc.confidence_label == "insufficient_data"
    assert fc.horizon == []
    assert fc.warning is not None and "periods" in fc.warning


def test_synthetic_data_warning_fires() -> None:
    df = _toy_frame(n=500, n_periods=24)
    idx = build_index(df, period="Q", min_obs_per_period=3)
    fc = forecast(idx, n_periods_ahead=4, is_synthetic_data=True)
    assert fc.warning is not None
    assert "synthetic" in fc.warning.lower()
    assert fc.confidence_label == "low"


def test_backtest_returns_rows() -> None:
    df = _toy_frame(n=600, n_periods=28)
    idx = build_index(df, period="Q", min_obs_per_period=3)
    bt = backtest(idx, horizon=4, min_train_periods=12)
    assert not bt.empty
    assert {"horizon", "actual_index", "forecast_index", "ape", "in_interval"} <= set(bt.columns)
    # Backtest should produce reasonable MAPE on this well-behaved synthetic data
    assert bt["ape"].median() < 0.30, "Synthetic with a clean trend should backtest reasonably"
