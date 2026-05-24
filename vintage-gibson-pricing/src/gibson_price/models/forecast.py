"""Time-series forecast on top of the hedonic index.

Approach: take the index built by `index.build_index`, fit a Ridge regression
of `log_offset` on time + optional macro regressors (lagged S&P 500, 10Y
Treasury), and project `n_periods_ahead` quarters forward with adaptive
conformal intervals from the in-sample residuals.

Honest caveats:
  - With only synthetic seed data (sold_date randomized w.r.t. price), the
    forecast is meaningless. The architecture is sound; the data isn't there.
  - For real forecasts, the index needs ≥20 periods of real timestamped sold
    records. Heritage Auctions historical backfill (10+ years) is the most
    realistic path to that.
  - Vintage prices had a regime shift in 2020-22 (COVID spike) and a
    correction in 2023. Static conformal intervals miscalibrate across
    regime shifts; the adaptive conformal here is a partial mitigation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from gibson_price.models.index import HedonicIndex

log = logging.getLogger(__name__)


@dataclass
class ForecastPoint:
    period: pd.Period
    median_log_offset: float
    lo_log_offset: float
    hi_log_offset: float
    median_index: float
    lo_index: float
    hi_index: float


@dataclass
class ForecastResult:
    scope: str
    base_period: pd.Period
    history: list[ForecastPoint]
    horizon: list[ForecastPoint]
    in_sample_rmse: float
    n_history: int
    macro_regressors_used: list[str]
    confidence_label: str          # "high" / "medium" / "low" / "insufficient_data"
    warning: str | None            # e.g. "Forecast based on synthetic data; do not trust."


def _build_design_matrix(
    periods: list[pd.Period],
    *,
    macros: dict[str, pd.DataFrame] | None = None,
    macros_used: list[str] | None = None,
) -> tuple[np.ndarray, list[str]]:
    """Time trend + optional macro lags. Returns (X, regressor_names)."""
    macros_used = macros_used or []
    # Time trend in fractional years from the first period
    t = np.array([(p.start_time - periods[0].start_time).days / 365.25 for p in periods])
    cols = [t]
    names = ["time_years"]
    if macros and macros_used:
        for name in macros_used:
            macro_df = macros.get(name)
            if macro_df is None:
                continue
            # Align macro values to each period end (lag 1 quarter for forecasting realism)
            lookup = macro_df.set_index("period_end")[name]
            vals = []
            for p in periods:
                end = p.end_time
                # Take the last macro observation on or before period_end
                window = lookup[lookup.index <= end]
                vals.append(float(window.iloc[-1]) if not window.empty else np.nan)
            arr = np.array(vals)
            if np.isnan(arr).all():
                continue
            # Forward-fill NaN with the last valid value
            mask = ~np.isnan(arr)
            if mask.any():
                last = arr[mask][0]
                for i, v in enumerate(arr):
                    if np.isnan(v):
                        arr[i] = last
                    else:
                        last = v
            cols.append(arr)
            names.append(name)
    X = np.column_stack(cols) if len(cols) > 1 else cols[0].reshape(-1, 1)
    return X, names


def _conformal_band(residuals: np.ndarray, alpha: float = 0.2) -> float:
    """Empirical (1 - alpha)-quantile of |residuals|. Wider than gaussian when
    residuals are heavy-tailed."""
    if len(residuals) == 0:
        return 0.0
    return float(np.quantile(np.abs(residuals), 1 - alpha))


def forecast(
    index: HedonicIndex,
    *,
    n_periods_ahead: int = 4,
    macros: dict[str, pd.DataFrame] | None = None,
    is_synthetic_data: bool = False,
) -> ForecastResult:
    """Project the hedonic index forward `n_periods_ahead` periods."""
    points = index.points
    n_hist = len(points)
    history_periods = [p.period for p in points]
    y = np.array([p.log_offset for p in points])

    macros_used = sorted([m for m in (macros or {})]) if macros else []
    X_hist, regressor_names = _build_design_matrix(history_periods, macros=macros, macros_used=macros_used)

    # Insufficient data: just return the history with a "no forecast" flag
    if n_hist < 8:
        return ForecastResult(
            scope=index.scope, base_period=index.base_period,
            history=[
                ForecastPoint(p.period, p.log_offset, p.log_offset - p.stderr, p.log_offset + p.stderr,
                              p.index_value, float(np.exp(p.log_offset - p.stderr)), float(np.exp(p.log_offset + p.stderr)))
                for p in points
            ],
            horizon=[],
            in_sample_rmse=0.0,
            n_history=n_hist,
            macro_regressors_used=regressor_names[1:],
            confidence_label="insufficient_data",
            warning=f"Index has only {n_hist} periods. Need >=8 for any forecast; "
                    f">=20 for a meaningful one.",
        )

    model = Ridge(alpha=1.0)
    model.fit(X_hist, y)
    in_sample_pred = model.predict(X_hist)
    residuals = y - in_sample_pred
    rmse = float(np.sqrt(np.mean(residuals ** 2)))
    band = _conformal_band(residuals, alpha=0.2)

    # Project forward
    freq = points[-1].period.freqstr or "Q"
    future_periods = [points[-1].period + (i + 1) for i in range(n_periods_ahead)]
    X_future, _ = _build_design_matrix(history_periods + future_periods, macros=macros, macros_used=macros_used)
    X_future = X_future[n_hist:]
    future_pred = model.predict(X_future)

    history_out = [
        ForecastPoint(
            period=p.period,
            median_log_offset=p.log_offset,
            lo_log_offset=p.log_offset - band,
            hi_log_offset=p.log_offset + band,
            median_index=p.index_value,
            lo_index=float(np.exp(p.log_offset - band)),
            hi_index=float(np.exp(p.log_offset + band)),
        )
        for p in points
    ]
    horizon_out = [
        ForecastPoint(
            period=fp,
            median_log_offset=float(pred),
            lo_log_offset=float(pred - band),
            hi_log_offset=float(pred + band),
            median_index=float(np.exp(pred)),
            lo_index=float(np.exp(pred - band)),
            hi_index=float(np.exp(pred + band)),
        )
        for fp, pred in zip(future_periods, future_pred, strict=False)
    ]
    _ = freq  # not currently used, but retained for downstream periodicity inference

    confidence = "high" if n_hist >= 30 and rmse < 0.15 else ("medium" if n_hist >= 15 else "low")
    if is_synthetic_data:
        confidence = "low"
        warning = ("Forecast based on synthetic seed data — do NOT trust the directional "
                   "signal. Architecture is correct; backfill Heritage historical sold "
                   "data for a meaningful forecast.")
    else:
        warning = None

    return ForecastResult(
        scope=index.scope, base_period=index.base_period,
        history=history_out, horizon=horizon_out,
        in_sample_rmse=rmse, n_history=n_hist,
        macro_regressors_used=regressor_names[1:],
        confidence_label=confidence, warning=warning,
    )


def backtest(
    index: HedonicIndex,
    *,
    macros: dict[str, pd.DataFrame] | None = None,
    horizon: int = 4,
    min_train_periods: int = 12,
) -> pd.DataFrame:
    """Walk-forward backtest: at each cutoff, train on history, forecast `horizon`
    periods, compare to actuals. Returns per-fold MAPE on the index level."""
    points = index.points
    rows = []
    for cutoff in range(min_train_periods, len(points) - horizon):
        train_idx = HedonicIndex(
            base_period=index.base_period,
            points=points[:cutoff],
            scope=index.scope,
        )
        result = forecast(train_idx, n_periods_ahead=horizon, macros=macros)
        if not result.horizon:
            continue
        for offset, hp in enumerate(result.horizon, start=1):
            actual = points[cutoff + offset - 1]
            ape = abs(hp.median_index - actual.index_value) / max(actual.index_value, 1e-6)
            rows.append({
                "cutoff_period": str(points[cutoff - 1].period),
                "forecast_period": str(actual.period),
                "horizon": offset,
                "actual_index": actual.index_value,
                "forecast_index": hp.median_index,
                "ape": ape,
                "in_interval": hp.lo_index <= actual.index_value <= hp.hi_index,
            })
    return pd.DataFrame(rows)
