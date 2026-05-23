"""Training pipeline.

Steps:
  1. Load all ingest sources into a unified DataFrame.
  2. Forward-chaining time split: train on oldest, calibrate on middle, hold out newest.
  3. Fit LightGBM on log(price).
  4. Fit CQR for 80% prediction intervals.
  5. Fit hierarchical residual model for per-(model_family x era) shrinkage.
  6. Persist the artifact bundle to disk.
  7. Emit `reports/eval.html` with calibration plots and per-family MAPE.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from gibson_price.features.build import build_feature_frame
from gibson_price.ingest.vg_price_guide import load_seed
from gibson_price.models.conformal import CQRModel, empirical_coverage, fit_cqr
from gibson_price.models.gbm import GBMConfig, predict_log, train_gbm
from gibson_price.models.hierarchical import HierarchicalResidualModel, fit_hierarchical
from gibson_price.schema import ALL_FEATURES

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PATH = ROOT / "artifacts" / "model.pkl"
EVAL_REPORT = ROOT / "reports" / "eval.html"
SEED_PATH = ROOT / "data" / "seed" / "gibson_acoustic_seed.csv"


@dataclass
class TrainingArtifact:
    gbm: object
    cqr: CQRModel
    hier: HierarchicalResidualModel
    data_sha: str
    n_rows: int
    n_train: int
    n_calib: int
    n_test: int
    test_mape: float
    test_rmse_log: float
    coverage_80: float
    per_family_mape: dict


def _data_sha(df: pd.DataFrame) -> str:
    csv_bytes = df.to_csv(index=False).encode()
    return hashlib.sha256(csv_bytes).hexdigest()[:16]


def _time_split(df: pd.DataFrame, train_frac: float = 0.7, calib_frac: float = 0.15) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("sold_year").reset_index(drop=True)
    n = len(df)
    n_train = int(n * train_frac)
    n_calib = int(n * calib_frac)
    train = df.iloc[:n_train]
    calib = df.iloc[n_train:n_train + n_calib]
    test = df.iloc[n_train + n_calib:]
    return train, calib, test


def _mape(y_true_usd: np.ndarray, y_pred_usd: np.ndarray) -> float:
    return float(np.mean(np.abs(y_pred_usd - y_true_usd) / np.maximum(y_true_usd, 1e-6)))


def _bias_correction(residuals_log: np.ndarray) -> float:
    """Empirical bias correction for log->dollar back-transform (Duan smearing on residuals)."""
    if len(residuals_log) == 0:
        return 1.0
    return float(np.mean(np.exp(residuals_log)))


def train_full(seed_path: Path = SEED_PATH) -> TrainingArtifact:
    log.info("Loading seed from %s", seed_path)
    listings = load_seed(seed_path)
    df = build_feature_frame(listings)
    if df.empty:
        raise RuntimeError("No training rows after feature build.")
    log.info("Built feature frame: %d rows", len(df))

    data_sha = _data_sha(df)
    train_df, calib_df, test_df = _time_split(df)

    X_cols = list(ALL_FEATURES)
    y_train_log = np.log(train_df["price_usd"].to_numpy())
    y_calib_log = np.log(calib_df["price_usd"].to_numpy())
    y_test_log = np.log(test_df["price_usd"].to_numpy())
    y_test_usd = test_df["price_usd"].to_numpy()

    gbm = train_gbm(
        train_df[X_cols],
        y_train_log,
        config=GBMConfig(),
        eval_set=(calib_df[X_cols], y_calib_log) if len(calib_df) > 0 else None,
    )

    # CQR for prediction intervals
    cqr = fit_cqr(train_df[X_cols], y_train_log, calib_df[X_cols], y_calib_log, alpha=0.2)

    # Hierarchical residual model
    train_pred_log = predict_log(gbm, train_df[X_cols])
    train_resid = y_train_log - train_pred_log
    hier = fit_hierarchical(train_df, train_resid)

    # Evaluate on holdout
    test_pred_log = predict_log(gbm, test_df[X_cols])
    test_hier_adj = hier.predict(test_df)
    bias = _bias_correction(y_train_log - train_pred_log)
    test_pred_usd = np.exp(test_pred_log + test_hier_adj) * bias

    test_mape = _mape(y_test_usd, test_pred_usd)
    test_rmse_log = float(np.sqrt(np.mean((y_test_log - test_pred_log) ** 2)))
    coverage = empirical_coverage(cqr, test_df[X_cols], y_test_log)

    per_family = (
        pd.DataFrame({
            "model_family": test_df["model_family"].values,
            "ape": np.abs(test_pred_usd - y_test_usd) / np.maximum(y_test_usd, 1e-6),
        })
        .groupby("model_family")["ape"]
        .mean()
        .round(3)
        .to_dict()
    )

    artifact = TrainingArtifact(
        gbm=gbm,
        cqr=cqr,
        hier=hier,
        data_sha=data_sha,
        n_rows=len(df),
        n_train=len(train_df),
        n_calib=len(calib_df),
        n_test=len(test_df),
        test_mape=test_mape,
        test_rmse_log=test_rmse_log,
        coverage_80=coverage,
        per_family_mape=per_family,
    )

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_PATH, "wb") as f:
        pickle.dump(artifact, f)

    _write_eval_report(artifact, train_df, test_df, test_pred_usd, y_test_usd, cqr, y_test_log)
    log.info("Saved artifact to %s", ARTIFACT_PATH)
    log.info("Test MAPE %.3f | RMSE(log) %.3f | 80%% coverage %.3f", test_mape, test_rmse_log, coverage)
    return artifact


def _write_eval_report(
    artifact: TrainingArtifact,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    pred_usd: np.ndarray,
    true_usd: np.ndarray,
    cqr: CQRModel,
    y_test_log: np.ndarray,
) -> None:
    EVAL_REPORT.parent.mkdir(parents=True, exist_ok=True)
    pi_lo, pi_hi = cqr.predict_interval(test_df)
    in_interval = ((y_test_log >= pi_lo) & (y_test_log <= pi_hi)).mean()

    body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>gibson-price eval</title>
<style>body{{font-family:system-ui,sans-serif;max-width:880px;margin:2rem auto;color:#111}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:.4rem .6rem;border-bottom:1px solid #eee;text-align:left}}
.metric{{display:inline-block;margin:.3rem 1rem .3rem 0;padding:.5rem .8rem;border-radius:6px;background:#f6f6f8}}
.k{{color:#666;font-size:.85rem}}.v{{font-size:1.4rem;font-weight:600}}</style></head><body>
<h1>gibson-price training report</h1>
<p class="k">Data SHA: <code>{artifact.data_sha}</code> &mdash; {artifact.n_rows} total rows ({artifact.n_train} train, {artifact.n_calib} calib, {artifact.n_test} test).</p>

<h2>Holdout metrics</h2>
<div class="metric"><div class="k">MAPE</div><div class="v">{artifact.test_mape:.1%}</div></div>
<div class="metric"><div class="k">RMSE (log)</div><div class="v">{artifact.test_rmse_log:.3f}</div></div>
<div class="metric"><div class="k">80% PI coverage</div><div class="v">{artifact.coverage_80:.1%}</div></div>
<div class="metric"><div class="k">PI coverage (USD-space)</div><div class="v">{in_interval:.1%}</div></div>

<h2>Per-model-family MAPE</h2>
<table><tr><th>model_family</th><th>MAPE</th></tr>
{"".join(f"<tr><td>{k}</td><td>{v:.1%}</td></tr>" for k, v in sorted(artifact.per_family_mape.items(), key=lambda x: -x[1]))}
</table>

<h2>Calibration target</h2>
<p>The 80% prediction interval should cover ~80% of holdout points (target band 75-85%).
A value far from 80% indicates miscalibration that the conformal correction did not fully absorb.</p>

<h2>Methodology</h2>
<ol>
  <li>LightGBM regressor on log(price) with native categorical handling.</li>
  <li>Forward-chaining time split (oldest 70% train, middle 15% calibration, newest 15% test) to avoid leaking the 2020-22 COVID regime shift.</li>
  <li>Conformalized Quantile Regression (CQR) on the calibration set for the 80% interval.</li>
  <li>Empirical-Bayes hierarchical shrinkage on residuals by (model_family x era_segment).</li>
  <li>Duan-smearing bias correction on the log -&gt; dollar back-transform.</li>
</ol>
</body></html>
"""
    EVAL_REPORT.write_text(body)
    log.info("Wrote eval report to %s", EVAL_REPORT)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    artifact = train_full()
    print(json.dumps({
        "data_sha": artifact.data_sha,
        "n_rows": artifact.n_rows,
        "test_mape": round(artifact.test_mape, 4),
        "test_rmse_log": round(artifact.test_rmse_log, 4),
        "coverage_80": round(artifact.coverage_80, 4),
    }, indent=2))


if __name__ == "__main__":
    main()
