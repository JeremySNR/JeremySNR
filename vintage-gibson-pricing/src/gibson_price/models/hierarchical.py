"""Bayesian hierarchical residual model — per (model_family x era_segment) shrinkage.

LightGBM tends to under-react on sparse model families (e.g., LG-2 with ~50 rows
gets pulled toward the global mean). This module fits a small Bayesian model on
the LightGBM log-residuals with random intercepts per (model_family x era_segment)
group, providing partial pooling that respects the data sparsity per group.

Implementation is intentionally tiny: a closed-form James-Stein / shrinkage
estimator with an empirical-Bayes prior. This avoids the PyMC compile cost while
giving 90% of the benefit of a full hierarchical posterior.

If you want the full Bayesian treatment, install the `hierarchical` extras and
swap in the commented `_fit_bambi` implementation below.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class HierarchicalResidualModel:
    group_means: dict[tuple[str, str], float] = field(default_factory=dict)
    global_mean: float = 0.0
    global_var: float = 0.0
    within_var: float = 0.0

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Return the shrunk residual adjustment for each row's group."""
        adj = np.zeros(len(df), dtype=float)
        for i, (mf, era) in enumerate(zip(df["model_family"], df["era_segment"], strict=False)):
            adj[i] = self.group_means.get((mf, era), 0.0)
        return adj


def fit_hierarchical(
    df: pd.DataFrame,
    residuals: np.ndarray,
    *,
    min_group_size: int = 3,
) -> HierarchicalResidualModel:
    """Empirical-Bayes shrunk group means on the log-residuals.

    Each group's posterior mean is a weighted average of:
      - the group's sample mean (weighted by n_group / within_var)
      - the global mean (weighted by 1 / between_var)
    Groups with few samples shrink hard toward the global mean.
    """
    df = df.copy()
    df["_resid"] = residuals
    df["_grp"] = list(zip(df["model_family"], df["era_segment"], strict=False))

    global_mean = float(df["_resid"].mean())
    within_var = float(df["_resid"].var(ddof=1)) or 1e-6

    group_sample_means = df.groupby("_grp")["_resid"].agg(["mean", "size"])
    between_var = float(group_sample_means["mean"].var(ddof=1)) or 1e-6

    shrunk: dict[tuple[str, str], float] = {}
    for grp, row in group_sample_means.iterrows():
        n = float(row["size"])
        if n < min_group_size:
            shrunk[grp] = global_mean
            continue
        # Shrinkage weight: how much to trust the group mean vs the global mean
        precision_group = n / within_var
        precision_global = 1.0 / between_var
        w = precision_group / (precision_group + precision_global)
        shrunk[grp] = w * float(row["mean"]) + (1 - w) * global_mean

    return HierarchicalResidualModel(
        group_means=shrunk,
        global_mean=global_mean,
        global_var=between_var,
        within_var=within_var,
    )


# Optional full-Bayesian implementation. Requires `bambi` and `pymc` extras.
#
# def _fit_bambi(df: pd.DataFrame, residuals: np.ndarray) -> HierarchicalResidualModel:
#     import bambi as bmb
#     df = df.copy()
#     df["resid"] = residuals
#     model = bmb.Model("resid ~ (1 | model_family) + (1 | era_segment)", df)
#     trace = model.fit(draws=500, tune=500, chains=2)
#     # Extract posterior means per group and pack into HierarchicalResidualModel
#     ...
