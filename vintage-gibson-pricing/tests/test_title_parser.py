"""Tests for the dealer-listing title parser."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gibson_price.ingest.title_parser import parse_title


def test_canonical_title() -> None:
    """Year, brand, model in standard order."""
    p = parse_title("1956 Gibson J-45 Sunburst")
    assert p.year == 1956
    assert p.brand == "Gibson"
    assert p.model_family == "J-45"
    assert p.confidence > 0.85


def test_brand_model_year_order() -> None:
    p = parse_title("Gibson J-45 1956 — Excellent Original")
    assert p.year == 1956
    assert p.brand == "Gibson"
    assert p.model_family == "J-45"


def test_uppercase_dealer_style() -> None:
    p = parse_title("GIBSON J-45 1956 EXC ORIG")
    assert p.brand == "Gibson"
    assert p.model_family == "J-45"
    assert p.year == 1956


def test_parenthesized_year() -> None:
    p = parse_title("Martin D-28 (1939) Brazilian Rosewood")
    assert p.brand == "Martin"
    assert p.model_family == "D-28"
    assert p.year == 1939


def test_pre_war_d45() -> None:
    p = parse_title("1936 Martin D-45 — holy grail")
    assert p.brand == "Martin"
    assert p.model_family == "D-45"
    assert p.year == 1936


def test_sj_200_variant_spelling() -> None:
    """Dealers use both J-200 and SJ-200 interchangeably."""
    p = parse_title("1952 Gibson SJ-200 Maple")
    assert p.model_family == "SJ-200"


def test_hummingbird_canonical_case() -> None:
    """Hummingbird in title -> 'Hummingbird' in catalog (not all-caps)."""
    p = parse_title("1962 Gibson Hummingbird Cherry Sunburst")
    assert p.model_family == "Hummingbird"
    assert p.brand == "Gibson"


def test_unknown_model_returns_none() -> None:
    p = parse_title("1965 Acme Stratospheric Mk II")
    assert p.brand is None or p.model_family is None
    assert p.confidence < 0.5


def test_confidence_drops_when_year_missing() -> None:
    p = parse_title("Gibson J-45 (year unknown)")
    assert p.brand == "Gibson"
    assert p.model_family == "J-45"
    assert p.year is None
    assert p.confidence < 0.85


def test_empty_input() -> None:
    p = parse_title("")
    assert p.year is None
    assert p.brand is None
    assert p.model_family is None
    assert p.confidence == 0.0


def test_lg_2_with_space_variant() -> None:
    """Dealers sometimes write 'LG 2' or 'LG2'."""
    p = parse_title("1953 Gibson LG-2 Sunburst")
    assert p.model_family == "LG-2"
