"""Extract (year, brand, model_family) from messy vintage dealer listing titles.

Vintage titles vary wildly:
  "1956 Gibson J-45 Sunburst"
  "Gibson J-45 1956 — Mahogany / Sitka"
  "GIBSON J-45 1956 EXC ORIG"
  "1942 Gibson J-45 Banner"
  "Martin D-28 (1939) Brazilian"

Approach: regex for year and brand (high precision), rapidfuzz for model_family
(handles "J45", "J 45", "J-45", "Jumbo 45"). Returns a confidence score so
downstream consumers can filter low-quality extractions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from gibson_price.schema import (
    GIBSON_MODELS,
    GRETSCH_MODELS,
    GUILD_MODELS,
    MARTIN_MODELS,
    Brand,
)

ALL_MODELS_BY_BRAND: dict[Brand, set[str]] = {
    "Gibson": GIBSON_MODELS,
    "Martin": MARTIN_MODELS,
    "Guild": GUILD_MODELS,
    "Gretsch": GRETSCH_MODELS,
}
ALL_MODELS_FLAT = [m for s in ALL_MODELS_BY_BRAND.values() for m in s]

_YEAR_RE = re.compile(r"\b(19[0-9]{2}|20[0-2][0-9])\b")
_BRAND_PATTERNS: list[tuple[re.Pattern[str], Brand]] = [
    (re.compile(r"\bgibson\b", re.I), "Gibson"),
    (re.compile(r"\bmartin\b", re.I), "Martin"),
    (re.compile(r"\bguild\b", re.I), "Guild"),
    (re.compile(r"\bgretsch\b", re.I), "Gretsch"),
    (re.compile(r"\bepiphone\b", re.I), "Epiphone"),
]


@dataclass
class TitleParse:
    year: int | None
    brand: Brand | None
    model_family: str | None
    confidence: float


def _normalize_for_fuzzy(s: str) -> str:
    """Collapse 'J 45' / 'J45' / 'J-45' to a single form for fuzzy matching."""
    return re.sub(r"\s+", "", s).replace("-", "").upper()


def parse_title(title: str) -> TitleParse:
    if not title:
        return TitleParse(year=None, brand=None, model_family=None, confidence=0.0)

    # Brand
    brand: Brand | None = None
    for pat, b in _BRAND_PATTERNS:
        if pat.search(title):
            brand = b
            break

    # Year — pick the most plausible (most common case is just one)
    years = [int(m.group(1)) for m in _YEAR_RE.finditer(title)]
    plausible = [y for y in years if 1920 <= y <= 2030]
    year = plausible[0] if plausible else None

    # Model family — try the candidate set for the inferred brand first
    candidates = list(ALL_MODELS_BY_BRAND.get(brand, set())) if brand else ALL_MODELS_FLAT
    norm_title = _normalize_for_fuzzy(title)
    best_model: str | None = None
    best_score = 0.0
    for cand in candidates:
        norm_cand = _normalize_for_fuzzy(cand)
        # Substring match wins outright
        if norm_cand in norm_title:
            best_model = cand
            best_score = 1.0
            break
    if best_model is None and candidates:
        result = process.extractOne(
            norm_title,
            [_normalize_for_fuzzy(c) for c in candidates],
            scorer=fuzz.partial_ratio,
            score_cutoff=85,
        )
        if result:
            _, score, idx = result
            best_model = candidates[idx]
            best_score = float(score) / 100.0

    # Confidence is the product of components found, weighted
    components = [
        (1.0 if brand else 0.0, 0.35),
        (1.0 if year else 0.0, 0.25),
        (best_score, 0.40),
    ]
    confidence = sum(v * w for v, w in components)

    return TitleParse(year=year, brand=brand, model_family=best_model, confidence=confidence)
