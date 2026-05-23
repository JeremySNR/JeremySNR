"""Gibson serial number and FON (Factory Order Number) dating.

References: Reverb's Gibson dating guide, truevintageguitar.com Gibson lookup,
Gibson's official serial-number documentation.

Coverage is intentionally pragmatic — covers the eras with high collector
value (1935-1985). Modern 8/9-digit codes (1977+) are decoded from the
digit positions per Gibson's published scheme.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FON_LETTER_TO_YEAR: dict[str, int] = {
    "A": 1935, "B": 1936, "C": 1937, "D": 1938, "E": 1939, "F": 1940,
    "G": 1941, "H": 1942, "J": 1943,
    # 1944-1946 used no letter prefix (numbers only).
    "S": 1955, "T": 1956, "U": 1957, "V": 1958, "W": 1959, "X": 1960, "Y": 1961,
    "Z": 1961,
}

NUMERIC_FON_RANGES: list[tuple[int, int, int]] = [
    (100, 1000, 1944),
    (1000, 2000, 1945),
    (2000, 3000, 1946),
    (3000, 5000, 1947),
    (5000, 6000, 1948),
    (6000, 8000, 1949),
    (8000, 9000, 1950),
    (9000, 9999, 1951),
]

SOLID_YEAR_SERIAL_RANGES: list[tuple[int, int, int]] = [
    (100, 99999, 1953),
    (100000, 199999, 1961),
    (200000, 299999, 1964),
    (300000, 499999, 1965),
    (500000, 599999, 1966),
    (600000, 999999, 1967),
]


@dataclass
class DatingResult:
    year: int | None
    method: str
    confidence: float


def date_gibson(serial_or_fon: str | None) -> DatingResult:
    """Best-effort year inference from a Gibson serial number or FON."""
    if not serial_or_fon:
        return DatingResult(year=None, method="missing", confidence=0.0)

    raw = serial_or_fon.strip().upper().replace("-", "").replace(" ", "")

    fon_match = re.match(r"^([A-Z])\s?(\d+)$", raw)
    if fon_match:
        letter = fon_match.group(1)
        year = FON_LETTER_TO_YEAR.get(letter)
        if year:
            return DatingResult(year=year, method="fon_letter", confidence=0.9)

    if raw.isdigit() and 1 <= len(raw) <= 5:
        n = int(raw)
        for lo, hi, yr in NUMERIC_FON_RANGES:
            if lo <= n < hi:
                return DatingResult(year=yr, method="fon_numeric_range", confidence=0.7)

    if raw.isdigit() and len(raw) in (8, 9):
        # Modern Gibson (1977-present): YDDDYNNN or YDDDYRRR variations.
        # The first digit + 5th digit form the year: e.g. 8 0 6 0 1 0 1 2 3 -> 1983.
        try:
            y1 = int(raw[0])
            y5 = int(raw[4])
            two_digit_year = y1 * 10 + y5
            year = 1900 + two_digit_year if two_digit_year >= 77 else 2000 + two_digit_year
            if 1977 <= year <= 2099:
                return DatingResult(year=year, method="modern_8or9digit", confidence=0.85)
        except (ValueError, IndexError):
            pass

    if raw.isdigit() and 5 <= len(raw) <= 6:
        n = int(raw)
        for lo, hi, yr in SOLID_YEAR_SERIAL_RANGES:
            if lo <= n <= hi:
                return DatingResult(year=yr, method="solid_year_serial_range", confidence=0.6)

    return DatingResult(year=None, method="unrecognized", confidence=0.0)


def year_from_listing(serial: str | None, listing_year: int | None) -> int | None:
    """Prefer an explicit listing year, fall back to decoded serial."""
    if listing_year and 1920 <= listing_year <= 2099:
        return listing_year
    decoded = date_gibson(serial)
    return decoded.year
