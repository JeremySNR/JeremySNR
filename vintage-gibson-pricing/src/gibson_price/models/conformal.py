"""Conformalized Quantile Regression (CQR) for calibrated prediction intervals.

We train LightGBM with `objective=quantile, alpha=q` for q in {0.1, 0.5, 0.9},
then apply a split-conformal correction on a calibration set so the resulting
intervals achieve the nominal coverage on exchangeable data.

Reference: Romano, Patterson, Candès (2019) "Conformalized Quantile Regression".

We use a lightweight in-module implementation rather than mapie to avoid the
heavier sklearn-API constraints — the algorithm is short enough that a direct
implementation is clearer and more flexible.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from gibson_price.models.gbm import GBMConfig, _prepare
from gibson_price.schema import ALL_FEATURES, CATEGORICAL_FEATURES


@dataclass
class CQRModel:
    lo: lgb.LGBMRegressor
    hi: lgb.LGBMRegressor
    correction: float
    alpha: float

    def predict_interval(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        Xp = _prepare(X[list(ALL_FEATURES)])
        q_lo = self.lo.predict(Xp) - self.correction
        q_hi = self.hi.predict(Xp) + self.correction
        return q_lo, q_hi


def _train_quantile(
    X: pd.DataFrame,
    y_log: np.ndarray,
    alpha: float,
    config: GBMConfig,
) -> lgb.LGBMRegressor:
    model = lgb.LGBMRegressor(
        objective="quantile",
        alpha=alpha,
        n_estimators=config.n_estimators,
        learning_rate=config.learning_rate,
        num_leaves=config.num_leaves,
        min_data_in_leaf=config.min_data_in_leaf,
        feature_fraction=config.feature_fraction,
        bagging_fraction=config.bagging_fraction,
        bagging_freq=config.bagging_freq,
        lambda_l2=config.lambda_l2,
        random_state=config.random_state,
        verbose=-1,
    )
    Xp = _prepare(X[list(ALL_FEATURES)])
    model.fit(Xp, y_log, categorical_feature=list(CATEGORICAL_FEATURES))
    return model


def fit_cqr(
    X_train: pd.DataFrame,
    y_train_log: np.ndarray,
    X_calib: pd.DataFrame,
    y_calib_log: np.ndarray,
    *,
    alpha: float = 0.2,  # 1 - target coverage; 0.2 -> 80% PI
    config: GBMConfig | None = None,
) -> CQRModel:
    cfg = config or GBMConfig()
    lo_alpha = alpha / 2
    hi_alpha = 1 - alpha / 2

    lo = _train_quantile(X_train, y_train_log, lo_alpha, cfg)
    hi = _train_quantile(X_train, y_train_log, hi_alpha, cfg)

    Xc = _prepare(X_calib[list(ALL_FEATURES)])
    q_lo_calib = lo.predict(Xc)
    q_hi_calib = hi.predict(Xc)

    # Conformity scores: how far outside the predicted interval is the true value
    scores = np.maximum(q_lo_calib - y_calib_log, y_calib_log - q_hi_calib)
    n = len(scores)
    if n == 0:
        correction = 0.0
    else:
        k = int(np.ceil((n + 1) * (1 - alpha))) - 1
        k = max(0, min(k, n - 1))
        correction = float(np.sort(scores)[k])

    return CQRModel(lo=lo, hi=hi, correction=correction, alpha=alpha)


def empirical_coverage(model: CQRModel, X_test: pd.DataFrame, y_test_log: np.ndarray) -> float:
    lo, hi = model.predict_interval(X_test)
    inside = ((y_test_log >= lo) & (y_test_log <= hi)).mean()
    return float(inside)
