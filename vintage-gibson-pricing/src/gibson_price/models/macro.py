"""Macro signal pulling from FRED (Federal Reserve Economic Data) — free, no auth.

Vintage musical-instrument prices have documented correlations with:
  - S&P 500 (luxury-asset wealth effect)
  - 10-year Treasury yield (discount-rate driver; lower yields -> higher real-asset
    demand)
  - CPI / inflation (nominal-price drift)
  - M2 money supply (broader liquidity)
  - Art Market Index (when available; LiveAuctioneers and Artprice publish)

These are used as exogenous regressors in `forecast.py`. Pulling them is
optional — the forecast falls back to a pure time-trend model when FRED
data isn't available.

FRED CSV download format is `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>`
which is public and no-auth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import StringIO

import pandas as pd

from gibson_price.ingest.base import PolitenessConfig, make_session, polite_get

log = logging.getLogger(__name__)

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

CFG = PolitenessConfig(
    cache_name="fred",
    expire_after_seconds=60 * 60 * 24,
    rate_limit_seconds=1.0,
)
_session = make_session(CFG)


# Default series — IDs are FRED's. All have decades of daily/monthly history.
DEFAULT_SERIES: dict[str, str] = {
    "sp500": "SP500",          # S&P 500 daily close
    "treasury_10y": "DGS10",   # 10-year Treasury constant-maturity yield
    "cpi": "CPIAUCSL",         # CPI all urban consumers, monthly
    "m2": "M2SL",              # M2 monetary aggregate, monthly
}


@dataclass
class MacroSeries:
    name: str
    fred_id: str
    df: pd.DataFrame             # columns: date, value


def fetch_series(fred_id: str, *, name: str | None = None) -> MacroSeries | None:
    """Pull a FRED series as a tidy DataFrame."""
    resp = polite_get(_session, FRED_CSV, CFG, params={"id": fred_id})
    if resp is None or resp.status_code != 200:
        log.warning("FRED fetch failed for %s", fred_id)
        return None
    try:
        df = pd.read_csv(StringIO(resp.text))
    except (pd.errors.ParserError, ValueError) as e:
        log.warning("FRED parse failed for %s: %s", fred_id, e)
        return None
    # FRED CSVs use the series ID as the value column header
    value_col = df.columns[-1]
    df = df.rename(columns={df.columns[0]: "date", value_col: "value"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna()
    return MacroSeries(name=name or fred_id, fred_id=fred_id, df=df)


def fetch_default_macros() -> dict[str, MacroSeries]:
    """Pull the default macro panel. Returns a dict of name -> MacroSeries.
    Empty if the network is unavailable; callers handle the missing-data case."""
    out: dict[str, MacroSeries] = {}
    for name, fred_id in DEFAULT_SERIES.items():
        series = fetch_series(fred_id, name=name)
        if series is not None and not series.df.empty:
            out[name] = series
    return out


def align_to_period(series: MacroSeries, *, period: str = "Q") -> pd.DataFrame:
    """Resample a FRED series to the index's period (Q / M / Y) using period-mean."""
    s = series.df.set_index("date")["value"]
    resampled = s.resample(period).mean().dropna()
    return resampled.to_frame(name=series.name).reset_index().rename(columns={"date": "period_end"})
