"""Inference API used by both the CLI and the Streamlit demo.

predict_price() takes a structured PredictionRequest and returns a PricePrediction
with the median dollar value, 80% prediction interval, SHAP-based top-contributor
breakdown, and a natural-language summary.

If the trained model artifact cannot be loaded, falls back to comps_estimate()
over the seed CSV — so the app is never broken on cold start.
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from gibson_price.features.build import (
    BODY_SHAPE_BY_MODEL,
    bracing_pattern_for,
    bridge_type_for,
    era_segment,
    factory_for,
    hide_glue_for,
    tuner_type_for,
)
from gibson_price.features.tonewood import canon_back_sides, canon_top
from gibson_price.ingest.vg_price_guide import load_seed
from gibson_price.models.comps import comps_estimate
from gibson_price.models.explainer import explain_one, summarize_in_words
from gibson_price.models.gbm import predict_log
from gibson_price.schema import (
    ALL_FEATURES,
    ConditionGrade,
    PricePrediction,
    ShapContribution,
)

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PATH = ROOT / "artifacts" / "model.pkl"
SEED_PATH = ROOT / "data" / "seed" / "gibson_acoustic_seed.csv"


@dataclass
class PredictionRequest:
    brand: str
    model_family: str
    year: int
    condition_grade: int = int(ConditionGrade.VERY_GOOD)

    # Originality
    refinished: bool = False
    headstock_repaired: bool = False
    neck_reset: bool = False
    refret: bool = False
    replaced_tuners: bool = False
    replaced_bridge: bool = False
    replaced_pickup: bool = False
    replaced_pickguard: bool = False
    top_crack: bool = False
    side_crack: bool = False
    binding_shrinkage: bool = False

    # Provenance
    has_original_case: bool = False
    has_original_receipt: bool = False
    has_pre_war_certification: bool = False
    prior_famous_owner: bool = False

    # Construction overrides (default to era-appropriate)
    top_wood: str | None = None
    back_sides_wood: str | None = None
    finish: str = "Sunburst"
    sunburst_pattern: str = "Tobacco"

    sold_year: int = 2024


def _to_feature_row(req: PredictionRequest) -> pd.DataFrame:
    bracing, scalloped = bracing_pattern_for(req.brand, req.model_family, req.year)
    row = {
        "brand": req.brand,
        "model_family": req.model_family,
        "year": req.year,
        "era_segment": era_segment(req.year),
        "factory": factory_for(req.brand, req.year),
        "body_shape": BODY_SHAPE_BY_MODEL.get(req.model_family, "Unknown"),
        "top_wood": canon_top(req.top_wood, req.year),
        "back_sides_wood": canon_back_sides(req.back_sides_wood, req.model_family, req.year),
        "bracing_pattern": bracing,
        "bracing_scalloped": scalloped,
        "bridge_type": bridge_type_for(req.brand, req.model_family, req.year),
        "tuner_type": tuner_type_for(req.brand, req.year),
        "hide_glue_construction": hide_glue_for(req.brand, req.year),
        "finish": req.finish,
        "sunburst_pattern": req.sunburst_pattern,
        "condition_grade": int(req.condition_grade),
        "headstock_repaired": int(req.headstock_repaired),
        "neck_reset": int(req.neck_reset),
        "refret": int(req.refret),
        "top_crack": int(req.top_crack),
        "side_crack": int(req.side_crack),
        "binding_shrinkage": int(req.binding_shrinkage),
        "refinished": int(req.refinished),
        "replaced_tuners": int(req.replaced_tuners),
        "replaced_bridge": int(req.replaced_bridge),
        "replaced_pickup": int(req.replaced_pickup),
        "replaced_pickguard": int(req.replaced_pickguard),
        "has_original_case": int(req.has_original_case),
        "has_original_receipt": int(req.has_original_receipt),
        "has_pre_war_certification": int(req.has_pre_war_certification),
        "prior_famous_owner": int(req.prior_famous_owner),
        "source": "vg_guide",
        "sold_year": req.sold_year,
    }
    return pd.DataFrame([row], columns=list(ALL_FEATURES))


def _confidence_label(interval_width_ratio: float, n_comps: int) -> str:
    if interval_width_ratio < 0.5 and n_comps >= 5:
        return "high"
    if interval_width_ratio < 1.0 and n_comps >= 3:
        return "medium"
    return "low"


def _load_artifact():
    if not ARTIFACT_PATH.exists():
        return None
    try:
        with open(ARTIFACT_PATH, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        log.warning("Could not load model artifact: %s", e)
        return None


def predict_price(req: PredictionRequest) -> PricePrediction:
    artifact = _load_artifact()
    seed_df_listings = load_seed(SEED_PATH)
    from gibson_price.features.build import build_feature_frame
    seed_df = build_feature_frame(seed_df_listings)

    _, _, _, comps_df = comps_estimate(
        seed_df,
        brand=req.brand,
        model_family=req.model_family,
        year=req.year,
        condition_grade=req.condition_grade,
        refinished=req.refinished,
        k=5,
    )
    nearest_comps = comps_df[["brand", "model_family", "year", "condition_grade", "price_usd"]].to_dict("records") if not comps_df.empty else []

    if artifact is None:
        return _comps_fallback(req, seed_df, nearest_comps)

    X = _to_feature_row(req)
    pred_log = float(predict_log(artifact.gbm, X)[0])
    hier_adj = float(artifact.hier.predict(X)[0])
    median_log = pred_log + hier_adj
    median_usd = float(np.exp(median_log))

    lo, hi = artifact.cqr.predict_interval(X)
    lo_usd = float(np.exp(lo[0] + hier_adj))
    hi_usd = float(np.exp(hi[0] + hier_adj))

    shap_result = explain_one(artifact.gbm, X, median_usd)
    summary = summarize_in_words(shap_result.contributions, median_usd)

    width_ratio = (hi_usd - lo_usd) / max(median_usd, 1.0)
    confidence = _confidence_label(width_ratio, len(nearest_comps))

    return PricePrediction(
        median_usd=round(median_usd, -1),
        interval_low_usd=round(lo_usd, -1),
        interval_high_usd=round(hi_usd, -1),
        confidence_label=confidence,
        top_contributors=shap_result.contributions,
        natural_language_summary=summary,
        method="ml",
        nearest_comps=nearest_comps,
    )


def _comps_fallback(req: PredictionRequest, seed_df: pd.DataFrame, nearest_comps: list[dict]) -> PricePrediction:
    median, p10, p90, _ = comps_estimate(
        seed_df,
        brand=req.brand,
        model_family=req.model_family,
        year=req.year,
        condition_grade=req.condition_grade,
        refinished=req.refinished,
        k=8,
    )
    summary = f"Comps-only estimate (no trained model loaded). Median of {len(nearest_comps)} nearest comparables: ${median:,.0f}."
    return PricePrediction(
        median_usd=round(median, -1),
        interval_low_usd=round(p10, -1),
        interval_high_usd=round(p90, -1),
        confidence_label="low" if len(nearest_comps) < 4 else "medium",
        top_contributors=[
            ShapContribution(feature="model_family", value=req.model_family, contribution_usd=0.0),
        ],
        natural_language_summary=summary,
        method="comps_fallback",
        nearest_comps=nearest_comps,
    )
