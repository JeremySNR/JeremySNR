"""Market tab: index history + forecast + macro overlay.

Imported by `streamlit_app.py`. Builds the hedonic index from the loaded
seed (or, in real-data mode, from the merged ingest output) and projects
forward with `models.forecast`.

The synthetic-data warning is loud and permanent — anyone seeing the demo
should know the directional signal isn't real.
"""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from gibson_price.features.build import build_feature_frame
from gibson_price.ingest.vg_price_guide import load_seed
from gibson_price.models.forecast import forecast
from gibson_price.models.index import build_index

log = logging.getLogger(__name__)


SEED_NAMES = ("Gibson:J-45", "Gibson:Hummingbird", "Gibson:SJ-200",
              "Gibson:Southern Jumbo", "Martin:D-28", "all_gibson")


def _filter_scope(df: pd.DataFrame, scope: str) -> pd.DataFrame:
    if scope == "all_gibson":
        return df[df["brand"] == "Gibson"]
    brand, model = scope.split(":", 1)
    return df[(df["brand"] == brand) & (df["model_family"] == model)]


def render_market_tab(seed_path) -> None:
    st.header("📈 Market index & forecast")
    st.warning(
        "**Synthetic-data caveat.** This index is built from the 748-row seed "
        "CSV, whose `sold_date` was randomized independently of price. The "
        "architecture is real (hedonic index + Ridge forecast + conformal "
        "bands), but the *directional signal is meaningless*. A real forecast "
        "needs Heritage Auctions historical backfill (10+ years of real "
        "timestamped sold records) — see `MODEL_CARD.md`."
    )

    scope = st.selectbox(
        "Scope",
        SEED_NAMES,
        help="Pick a (brand, model) to build a condition-adjusted price index for.",
    )
    horizon = st.slider("Forecast horizon (quarters ahead)", 1, 8, 4)

    listings = load_seed(seed_path)
    df = build_feature_frame(listings)
    scoped = _filter_scope(df, scope)

    if len(scoped) < 30:
        st.info(
            f"Not enough records for scope `{scope}` "
            f"({len(scoped)} rows; need ≥30 for a usable index). "
            "Try `all_gibson` or run the live ingest to add more data."
        )
        return

    try:
        idx = build_index(scoped, period="Q", scope=scope, min_obs_per_period=5)
    except ValueError as e:
        st.info(str(e))
        return

    fc = forecast(idx, n_periods_ahead=horizon, is_synthetic_data=True)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Index periods", fc.n_history)
    col_b.metric("In-sample RMSE (log)", f"{fc.in_sample_rmse:.3f}")
    col_c.metric("Confidence", fc.confidence_label)
    if fc.warning:
        st.caption(f"⚠️ {fc.warning}")

    if not fc.horizon:
        st.write("No forecast — see warning above.")
        return

    rows = []
    for hp in fc.history:
        rows.append({
            "period": str(hp.period), "kind": "history",
            "index": hp.median_index, "lo": hp.lo_index, "hi": hp.hi_index,
        })
    for hp in fc.horizon:
        rows.append({
            "period": str(hp.period), "kind": "forecast",
            "index": hp.median_index, "lo": hp.lo_index, "hi": hp.hi_index,
        })
    chart_df = pd.DataFrame(rows)

    st.subheader(f"Index — base period {fc.base_period}")
    st.line_chart(chart_df.set_index("period")[["lo", "index", "hi"]])
    with st.expander("Underlying data"):
        st.dataframe(chart_df, use_container_width=True, hide_index=True)
