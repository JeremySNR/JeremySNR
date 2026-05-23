"""Tests for condition normalization, originality parsing, and tonewood inference."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gibson_price.features.condition import normalize_condition
from gibson_price.features.originality import parse_description
from gibson_price.features.tonewood import canon_back_sides, canon_top
from gibson_price.schema import ConditionGrade


def test_condition_mint_variants() -> None:
    assert normalize_condition("Mint") == ConditionGrade.MINT
    assert normalize_condition("brand new") == ConditionGrade.MINT
    assert normalize_condition("NOS — never played") == ConditionGrade.MINT


def test_condition_vg_plus_vs_vg() -> None:
    assert normalize_condition("VG+") == ConditionGrade.VERY_GOOD_PLUS
    assert normalize_condition("Very Good Plus") == ConditionGrade.VERY_GOOD_PLUS
    assert normalize_condition("VG") == ConditionGrade.VERY_GOOD
    assert normalize_condition("Very Good") == ConditionGrade.VERY_GOOD


def test_condition_unknown_returns_none() -> None:
    assert normalize_condition("¯\\_(ツ)_/¯") is None
    assert normalize_condition("") is None
    assert normalize_condition(None) is None


def test_originality_refinished_detection() -> None:
    sig = parse_description("Has been professionally refinished in nitrocellulose.")
    assert sig.refinished is True


def test_originality_headstock_break() -> None:
    sig = parse_description("Has a clean headstock break repair from the 1980s.")
    assert sig.headstock_repaired is True


def test_originality_neck_reset_and_refret() -> None:
    sig = parse_description("Recent neck reset and refretted with Jescar wire.")
    assert sig.neck_reset is True
    assert sig.refret is True


def test_originality_replaced_tuners() -> None:
    sig = parse_description("Replaced Grover tuners. Originals lost.")
    assert sig.replaced_tuners is True


def test_originality_original_case() -> None:
    sig = parse_description("Comes with original brown chipboard case and hang tag.")
    assert sig.has_original_case is True
    assert sig.has_original_receipt is True


def test_originality_clean_listing_has_no_flags() -> None:
    sig = parse_description("All original. Plays beautifully. No issues.")
    assert sig.refinished is False
    assert sig.headstock_repaired is False
    assert sig.refret is False


def test_tonewood_top_defaults_by_year() -> None:
    assert canon_top(None, 1940) == "Adirondack"
    assert canon_top(None, 1960) == "Sitka"
    assert canon_top("red spruce", 1960) == "Adirondack"  # explicit override


def test_tonewood_back_sides_by_model() -> None:
    assert canon_back_sides(None, "J-200", 1955) == "Maple"
    assert canon_back_sides(None, "D-28", 1955) == "Brazilian Rosewood"
    assert canon_back_sides(None, "D-28", 1975) == "Indian Rosewood"
    assert canon_back_sides(None, "J-45", 1950) == "Mahogany"
