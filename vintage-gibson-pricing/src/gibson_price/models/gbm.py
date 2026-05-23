"""LightGBM regressor on log(price). Native categorical handling."""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from gibson_price.schema import ALL_FEATURES, CATEGORICAL_FEATURES


@dataclass
class GBMConfig:
    n_estimators: int = 800
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_data_in_leaf: int = 8  # tuned low for sparse model families
    feature_fraction: float = 0.9
    bagging_fraction: float = 0.85
    bagging_freq: int = 5
    lambda_l2: float = 0.1
    random_state: int = 42


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure categorical columns are pandas categoricals so LightGBM uses native handling."""
    df = df.copy()
    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            df[col] = df[col].astype("category")
    return df


def train_gbm(
    X: pd.DataFrame,
    y_log: np.ndarray,
    *,
    config: GBMConfig | None = None,
    eval_set: tuple[pd.DataFrame, np.ndarray] | None = None,
) -> lgb.LGBMRegressor:
    cfg = config or GBMConfig()
    X = _prepare(X[list(ALL_FEATURES)])
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=cfg.n_estimators,
        learning_rate=cfg.learning_rate,
        num_leaves=cfg.num_leaves,
        min_data_in_leaf=cfg.min_data_in_leaf,
        feature_fraction=cfg.feature_fraction,
        bagging_fraction=cfg.bagging_fraction,
        bagging_freq=cfg.bagging_freq,
        lambda_l2=cfg.lambda_l2,
        random_state=cfg.random_state,
        verbose=-1,
    )
    fit_kwargs: dict = {"categorical_feature": list(CATEGORICAL_FEATURES)}
    if eval_set is not None:
        Xe, ye = eval_set
        Xe = _prepare(Xe[list(ALL_FEATURES)])
        fit_kwargs["eval_set"] = [(Xe, ye)]
        fit_kwargs["callbacks"] = [lgb.early_stopping(50, verbose=False)]
    model.fit(X, y_log, **fit_kwargs)
    return model


def predict_log(model: lgb.LGBMRegressor, X: pd.DataFrame) -> np.ndarray:
    X = _prepare(X[list(ALL_FEATURES)])
    return model.predict(X)
