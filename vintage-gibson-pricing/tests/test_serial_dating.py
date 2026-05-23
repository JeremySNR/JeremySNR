"""Verify Gibson serial / FON decoding against known examples."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gibson_price.features.gibson_serial import date_gibson, year_from_listing


def test_fon_letter_prefix_known_years() -> None:
    """FON letters A-J map to 1935-1943 per Gibson documentation."""
    assert date_gibson("A1234").year == 1935
    assert date_gibson("E2345").year == 1939
    assert date_gibson("H4567").year == 1942
    assert date_gibson("J0500").year == 1943


def test_fon_letter_postwar_resumption() -> None:
    """S-Z were used 1955-1961."""
    assert date_gibson("S1234").year == 1955
    assert date_gibson("V5678").year == 1958
    assert date_gibson("Y9000").year == 1961


def test_numeric_fon_postwar() -> None:
    """1944-1951 used no letter prefix, only numbers."""
    assert date_gibson("500").year == 1944
    assert date_gibson("1500").year == 1945
    assert date_gibson("8500").year == 1950


def test_modern_eight_digit_serial() -> None:
    """Modern 8-digit serials encode year in positions 1 and 5."""
    # YDDD Y NNN — first digit + 5th digit form the year
    # 8 0 0 1 3 0 1 2 -> year = 83
    result = date_gibson("80013012")
    assert result.year == 1983
    assert result.method == "modern_8or9digit"


def test_unrecognized_serial_returns_none() -> None:
    """Random gibberish should fail cleanly, not crash."""
    result = date_gibson("XYZ!!!")
    assert result.year is None
    assert result.confidence == 0.0


def test_none_input() -> None:
    """None / empty input should return method='missing'."""
    assert date_gibson(None).year is None
    assert date_gibson("").year is None
    assert date_gibson(None).method == "missing"


def test_year_from_listing_prefers_explicit_year() -> None:
    """An explicit year should win over a (potentially wrong) decoded serial."""
    assert year_from_listing("XYZ", 1956) == 1956


def test_year_from_listing_falls_back_to_serial() -> None:
    """Missing explicit year should decode from serial."""
    assert year_from_listing("A1234", None) == 1935


def test_year_from_listing_rejects_implausible() -> None:
    """Out-of-range years should not be accepted from the listing field."""
    assert year_from_listing("A1234", 1850) == 1935  # falls back to decoder
