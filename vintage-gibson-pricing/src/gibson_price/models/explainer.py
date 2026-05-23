"""SHAP TreeExplainer wrapper. Translates raw log-scale SHAP values into
dollar contributions and a natural-language summary."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import shap

from gibson_price.models.gbm import _prepare
from gibson_price.schema import ALL_FEATURES, ShapContribution

log = logging.getLogger(__name__)


@dataclass
class ShapResult:
    contributions: list[ShapContribution]
    base_value_usd: float


def explain_one(
    model,
    X_row: pd.DataFrame,
    median_usd: float,
    *,
    top_k: int = 6,
) -> ShapResult:
    """Compute SHAP values for a single row and convert to dollar contributions."""
    X = _prepare(X_row[list(ALL_FEATURES)])
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    base_log = float(explainer.expected_value)

    # SHAP values are on log-price scale. To translate to dollars, we apportion
    # the gap between predicted median and base-value-implied median proportionally.
    sv = shap_values[0] if shap_values.ndim > 1 else shap_values
    base_usd = float(np.exp(base_log))
    total_log_shift = float(sv.sum())
    scale = 0.0 if abs(total_log_shift) < 1e-9 else (median_usd - base_usd) / total_log_shift

    pairs = []
    row_vals = X_row.iloc[0]
    for feat, val in zip(ALL_FEATURES, sv, strict=False):
        contribution_usd = float(val * scale)
        if abs(contribution_usd) < 1.0:
            continue
        pairs.append(ShapContribution(
            feature=feat,
            value=str(row_vals[feat]),
            contribution_usd=round(contribution_usd, 2),
        ))
    pairs.sort(key=lambda p: abs(p.contribution_usd), reverse=True)
    return ShapResult(contributions=pairs[:top_k], base_value_usd=base_usd)


def summarize_in_words(contribs: list[ShapContribution], median_usd: float) -> str:
    """Render the top SHAP contributors as a short natural-language summary."""
    if not contribs:
        return f"Estimated value is ${median_usd:,.0f}. No single feature dominates."
    parts = []
    for c in contribs[:3]:
        sign = "adds" if c.contribution_usd > 0 else "subtracts"
        parts.append(f"{c.feature.replace('_', ' ')}={c.value} {sign} ~${abs(c.contribution_usd):,.0f}")
    return f"Estimated ${median_usd:,.0f}. Top drivers: " + "; ".join(parts) + "."
