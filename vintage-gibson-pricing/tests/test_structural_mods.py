"""Tests for the compound structural-modification fields and parsing.

These cover the 'what if a 40s guitar was retopped in the 60s' scenarios:
detecting alterations from listing descriptions, encoding them on FeatureRow,
and ensuring the era-distance feature is computed correctly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gibson_price.features.build import build_feature_frame
from gibson_price.features.originality import parse_description
from gibson_price.schema import ConditionGrade, GuitarListing

# ---------- regex / parser detection ----------

def test_retopped_phrase_detected() -> None:
    sig = parse_description("1942 Banner J-45 with a replacement top installed in 1968.")
    assert sig.top_replaced is True
    # Year hint should fall in the 1960s window
    assert sig.replacement_year_hint == 1968


def test_re_topped_short_form() -> None:
    sig = parse_description("Re-topped at some point; original mahogany back and sides.")
    assert sig.top_replaced is True


def test_back_sides_replaced() -> None:
    sig = parse_description("Original top and neck. Replacement back and sides in Brazilian.")
    assert sig.back_sides_replaced is True


def test_neck_graft_phrase() -> None:
    sig = parse_description("Has a documented neck graft from a 1953 donor neck.")
    assert sig.neck_replaced is True


def test_rebraced_phrase() -> None:
    sig = parse_description("Bracing converted to scalloped X-brace by Bryan Galloup.")
    assert sig.rebraced is True


def test_electrified_aftermarket_phrase() -> None:
    sig = parse_description("Installed pickup system (K&K Pure Mini) for stage use.")
    assert sig.electrified_aftermarket is True


def test_cutaway_conversion_phrase() -> None:
    sig = parse_description("Body converted to cutaway in the 1990s.")
    assert sig.converted_cutaway is True


def test_frankenguitar_phrase() -> None:
    sig = parse_description("This is a frankenguitar: 1956 neck on a 1962 body.")
    assert sig.frankenguitar is True


def test_clean_listing_no_alterations() -> None:
    sig = parse_description("All original. Plays beautifully. No issues.")
    assert sig.top_replaced is False
    assert sig.neck_replaced is False
    assert sig.rebraced is False
    assert sig.frankenguitar is False
    assert sig.replacement_year_hint is None


# ---------- feature encoding ----------

def test_era_distance_encoded() -> None:
    """1942 J-45 with a 1968 top -> era distance = 26 in the feature row."""
    listing = GuitarListing(
        source="vg_guide", source_listing_id="x", brand="Gibson", model_family="J-45",
        year=1942, condition_grade=ConditionGrade.VERY_GOOD,
        top_replaced=True, top_replacement_year=1968, price_usd=15000.0,
    )
    df = build_feature_frame([listing])
    assert df.iloc[0]["top_replaced"] == 1
    assert df.iloc[0]["top_replacement_era_distance"] == 26


def test_era_distance_zero_when_top_not_replaced() -> None:
    listing = GuitarListing(
        source="vg_guide", source_listing_id="x", brand="Gibson", model_family="J-45",
        year=1942, condition_grade=ConditionGrade.EXCELLENT, price_usd=22000.0,
    )
    df = build_feature_frame([listing])
    assert df.iloc[0]["top_replaced"] == 0
    assert df.iloc[0]["top_replacement_era_distance"] == 0


def test_all_alteration_flags_encoded_zero_by_default() -> None:
    """A clean listing should have all new alteration flags = 0."""
    listing = GuitarListing(
        source="vg_guide", source_listing_id="x", brand="Gibson", model_family="J-45",
        year=1955, condition_grade=ConditionGrade.EXCELLENT, price_usd=9000.0,
    )
    df = build_feature_frame([listing])
    row = df.iloc[0]
    for f in ("top_replaced", "back_sides_replaced", "neck_replaced", "rebraced",
              "body_repaired_major", "electrified_aftermarket", "converted_cutaway",
              "frankenguitar"):
        assert row[f] == 0, f"{f} should default to 0 on a clean listing"


def test_alteration_flag_from_description_propagates() -> None:
    """If the listing has no explicit boolean but the description mentions retopping,
    the parser should set the flag in the feature row."""
    listing = GuitarListing(
        source="vg_guide", source_listing_id="x", brand="Gibson", model_family="J-45",
        year=1942, condition_grade=ConditionGrade.GOOD,
        price_usd=8000.0,
        description="Original 1942 J-45 with a replacement top from 1968. Plays well.",
    )
    df = build_feature_frame([listing])
    assert df.iloc[0]["top_replaced"] == 1
    assert df.iloc[0]["top_replacement_era_distance"] == 26
