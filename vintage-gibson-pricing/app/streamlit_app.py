"""Streamlit web demo for the vintage Gibson pricing predictor.

Run locally:
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gibson_price.models.predict import PredictionRequest, predict_price  # noqa: E402
from gibson_price.schema import (  # noqa: E402
    GIBSON_MODELS,
    GRETSCH_MODELS,
    GUILD_MODELS,
    MARTIN_MODELS,
)

MODELS_BY_BRAND = {
    "Gibson": sorted(GIBSON_MODELS),
    "Martin": sorted(MARTIN_MODELS),
    "Guild": sorted(GUILD_MODELS),
    "Gretsch": sorted(GRETSCH_MODELS),
}

st.set_page_config(page_title="Vintage Acoustic Pricing", page_icon="🎸", layout="wide")

st.title("🎸 Vintage Acoustic Pricing — Gibson-focused")
st.caption(
    "Hedonic gradient-boosting model with conformalized 80% prediction intervals and "
    "SHAP-based explanations. Trained on a Vintage Guitar Price Guide / Heritage Auctions "
    "calibration set, weighted toward vintage Gibson acoustics."
)

col_input, col_output = st.columns([1, 1.4])

with col_input:
    st.subheader("Specify the guitar")
    brand = st.selectbox("Brand", list(MODELS_BY_BRAND.keys()), index=0)
    model_family = st.selectbox("Model", MODELS_BY_BRAND[brand], index=0)
    year = st.slider("Year", min_value=1928, max_value=2024, value=1955)
    condition = st.select_slider(
        "Condition",
        options=[("Poor", 1), ("Fair", 2), ("Good", 3), ("Very Good", 4),
                 ("Very Good+", 5), ("Excellent", 6), ("Mint", 7)],
        value=("Excellent", 6),
        format_func=lambda x: x[0],
    )

    st.markdown("**Originality** (each toggle subtracts value)")
    refinished = st.checkbox("Refinished / oversprayed")
    headstock_repaired = st.checkbox("Headstock break repaired")
    neck_reset = st.checkbox("Neck reset")
    refret = st.checkbox("Refretted")
    replaced_tuners = st.checkbox("Replaced tuners")
    replaced_bridge = st.checkbox("Replaced bridge")
    top_crack = st.checkbox("Top crack (repaired)")

    st.markdown("**Provenance** (each toggle adds value)")
    has_original_case = st.checkbox("Original case")
    has_original_receipt = st.checkbox("Original receipt / hang tag")
    prior_famous_owner = st.checkbox("Famous prior owner")

    if st.button("Estimate value", type="primary", use_container_width=True):
        st.session_state["last_request"] = PredictionRequest(
            brand=brand,
            model_family=model_family,
            year=year,
            condition_grade=condition[1],
            refinished=refinished,
            headstock_repaired=headstock_repaired,
            neck_reset=neck_reset,
            refret=refret,
            replaced_tuners=replaced_tuners,
            replaced_bridge=replaced_bridge,
            top_crack=top_crack,
            has_original_case=has_original_case,
            has_original_receipt=has_original_receipt,
            prior_famous_owner=prior_famous_owner,
        )

with col_output:
    req = st.session_state.get("last_request")
    if req is None:
        st.info("Specify a guitar on the left and click **Estimate value**.")
    else:
        with st.spinner("Predicting..."):
            pred = predict_price(req)

        st.subheader(f"Estimated value: **${pred.median_usd:,.0f}**")
        st.caption(
            f"80% prediction interval: ${pred.interval_low_usd:,.0f} — "
            f"${pred.interval_high_usd:,.0f}  •  confidence: {pred.confidence_label}  •  "
            f"method: `{pred.method}`"
        )
        st.write(pred.natural_language_summary)

        if pred.top_contributors:
            st.markdown("**Top price drivers (SHAP)**")
            shap_df = pd.DataFrame([
                {"feature": c.feature, "value": c.value, "contribution_usd": c.contribution_usd}
                for c in pred.top_contributors
            ])
            st.dataframe(shap_df, use_container_width=True, hide_index=True)

        if pred.nearest_comps:
            st.markdown("**Comparable comps from seed dataset**")
            comps_df = pd.DataFrame(pred.nearest_comps)
            st.dataframe(comps_df, use_container_width=True, hide_index=True)

        with st.expander("⚠️ Disclaimer"):
            st.write(
                "This is a portfolio demonstration, not a professional appraisal. "
                "Do not use this output for insurance valuation, sale negotiation, or "
                "any consequential financial decision. Vintage guitar valuation requires "
                "physical inspection by a qualified appraiser."
            )
