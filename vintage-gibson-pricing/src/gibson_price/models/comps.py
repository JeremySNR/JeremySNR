"""Comps-only fallback: nearest-neighbour lookup over the seed CSV.

Works with zero trained model — the day-one product. Returns the median
sale price of the K nearest comparable listings, along with the
neighbours themselves for display.

Used in two scenarios:
  1. As a baseline the ML model must beat (sanity check).
  2. As a fallback when the ML model can't be loaded (e.g., in the Streamlit
     app on cold start before the first training run).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gibson_price.schema import ConditionGrade


def find_comps(
    df: pd.DataFrame,
    *,
    brand: str,
    model_family: str,
    year: int,
    condition_grade: int = int(ConditionGrade.VERY_GOOD),
    refinished: bool = False,
    k: int = 8,
) -> pd.DataFrame:
    """Return the k nearest comparable listings from df, sorted by distance."""
    if df.empty:
        return df

    # Filter to same brand + model first; relax to brand-only if too few hits.
    primary = df[(df["brand"] == brand) & (df["model_family"] == model_family)]
    if len(primary) < k:
        primary = df[df["brand"] == brand]
    if len(primary) < k:
        primary = df

    candidates = primary.copy()
    candidates["_year_dist"] = (candidates["year"] - year).abs()
    candidates["_cond_dist"] = (candidates["condition_grade"] - condition_grade).abs()
    candidates["_refin_dist"] = (candidates["refinished"] - int(refinished)).abs() * 2
    candidates["_dist"] = (
        candidates["_year_dist"] * 0.5
        + candidates["_cond_dist"] * 3.0
        + candidates["_refin_dist"] * 5.0
    )
    return candidates.nsmallest(k, "_dist").drop(columns=["_year_dist", "_cond_dist", "_refin_dist", "_dist"])


def comps_estimate(
    df: pd.DataFrame,
    *,
    brand: str,
    model_family: str,
    year: int,
    condition_grade: int = int(ConditionGrade.VERY_GOOD),
    refinished: bool = False,
    k: int = 8,
) -> tuple[float, float, float, pd.DataFrame]:
    """Return (median, p10, p90, comps_df) from the k nearest neighbours."""
    comps = find_comps(
        df, brand=brand, model_family=model_family, year=year,
        condition_grade=condition_grade, refinished=refinished, k=k,
    )
    if comps.empty:
        return 0.0, 0.0, 0.0, comps
    prices = comps["price_usd"].values
    return (
        float(np.median(prices)),
        float(np.percentile(prices, 10)),
        float(np.percentile(prices, 90)),
        comps,
    )
