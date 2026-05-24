"""Condition-adjusted vintage guitar price index — Case-Shiller-inspired.

We can't run a true repeat-sales regression because we rarely see the same
serial number sold twice. Instead we build a hedonic index: at each time
window (quarter), fit a small LightGBM model that predicts log(price) from
the hedonic features, then track the residual offset over time. The offset
sequence is the market-level index.

This lets us decompose any historical sale into:
  log(price) = hedonic(features) + index(time) + noise

The hedonic part is constant; the index part is what we want to forecast.

For sparse model families we report a confidence interval on the index
itself based on the number of observations per window.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from gibson_price.models.gbm import _prepare
from gibson_price.schema import ALL_FEATURES, CATEGORICAL_FEATURES

log = logging.getLogger(__name__)


@dataclass
class IndexPoint:
    period: pd.Period
    n_obs: int
    log_offset: float        # mean log-residual in this window
    index_value: float       # multiplicative offset from baseline period
    stderr: float            # standard error of the mean residual


@dataclass
class HedonicIndex:
    base_period: pd.Period
    points: list[IndexPoint]
    scope: str               # e.g. "Gibson:J-45" or "Gibson:all"

    def as_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "period": str(p.period),
                "n_obs": p.n_obs,
                "log_offset": p.log_offset,
                "index_value": p.index_value,
                "stderr": p.stderr,
            }
            for p in self.points
        ])


def _train_hedonic_baseline(df: pd.DataFrame) -> lgb.LGBMRegressor:
    """Train a single LightGBM on the full dataset with `sold_year` removed,
    so the model captures only structural (feature) effects, not time effects."""
    feature_cols = [c for c in ALL_FEATURES if c != "sold_year"]
    X = _prepare(df[feature_cols])
    y = np.log(df["price_usd"].to_numpy())
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=31,
        min_data_in_leaf=8,
        random_state=42,
        verbose=-1,
    )
    cat = [c for c in CATEGORICAL_FEATURES if c != "sold_year"]
    model.fit(X, y, categorical_feature=cat)
    return model


def build_index(
    df: pd.DataFrame,
    *,
    period: str = "Q",           # quarterly bucketing; "M" or "Y" also fine
    scope: str = "all",
    min_obs_per_period: int = 5,
) -> HedonicIndex:
    """Construct a condition-adjusted index from timestamped sold records.

    Required columns: all ALL_FEATURES + `price_usd` + a sold_date convertible
    to a pandas Period (we derive it from `sold_year` if no explicit date).
    """
    if df.empty:
        raise ValueError("Cannot build index from empty DataFrame")

    df = df.copy()
    if "sold_date" not in df.columns:
        # Synthesize from sold_year only (loses sub-year resolution)
        df["sold_date"] = pd.to_datetime(df["sold_year"].astype(str) + "-06-30")
    else:
        df["sold_date"] = pd.to_datetime(df["sold_date"], errors="coerce")
    df = df.dropna(subset=["sold_date", "price_usd"])
    df["period"] = df["sold_date"].dt.to_period(period)

    baseline = _train_hedonic_baseline(df)
    feature_cols = [c for c in ALL_FEATURES if c != "sold_year"]
    X_all = _prepare(df[feature_cols])
    log_pred = baseline.predict(X_all)
    df["log_resid"] = np.log(df["price_usd"].to_numpy()) - log_pred

    points: list[IndexPoint] = []
    grouped = df.groupby("period")["log_resid"]
    for prd, residuals in grouped:
        n = len(residuals)
        if n < min_obs_per_period:
            continue
        log_off = float(residuals.mean())
        stderr = float(residuals.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0
        points.append(IndexPoint(
            period=prd, n_obs=n,
            log_offset=log_off,
            index_value=float(np.exp(log_off)),
            stderr=stderr,
        ))
    if not points:
        raise ValueError(
            f"No periods met min_obs_per_period={min_obs_per_period}. "
            f"Need more sold records before this index is meaningful."
        )

    base = points[0]
    for p in points:
        p.log_offset -= base.log_offset
        p.index_value = float(np.exp(p.log_offset))

    return HedonicIndex(base_period=base.period, points=points, scope=scope)
