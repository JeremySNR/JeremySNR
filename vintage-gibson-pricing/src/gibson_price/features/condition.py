"""Normalize free-text condition strings to the 7-point ordinal grade.

Aligns to Vintage Guitar Price Guide conventions:
  7 Mint, 6 Excellent, 5 Very Good Plus, 4 Very Good, 3 Good, 2 Fair, 1 Poor.

Reverb's "Mint / Excellent / Very Good / Good / Fair / Poor / Non-functioning"
collapses cleanly onto this scale.
"""

from __future__ import annotations

import re

from gibson_price.schema import ConditionGrade

_PATTERNS: list[tuple[re.Pattern[str], ConditionGrade]] = [
    (re.compile(r"\b(mint|brand[- ]?new|nos|new old stock|unplayed)\b", re.I), ConditionGrade.MINT),
    (re.compile(r"\b(near[- ]?mint|excellent\s*plus|excellent\+|nm)\b", re.I), ConditionGrade.EXCELLENT),
    (re.compile(r"\bexcellent\b", re.I), ConditionGrade.EXCELLENT),
    (re.compile(r"(\bvery\s*good\s*plus\b|\bvg\+)", re.I), ConditionGrade.VERY_GOOD_PLUS),
    (re.compile(r"\b(very\s*good|vg)\b", re.I), ConditionGrade.VERY_GOOD),
    (re.compile(r"\bgood\b", re.I), ConditionGrade.GOOD),
    (re.compile(r"\bfair\b", re.I), ConditionGrade.FAIR),
    (re.compile(r"\b(poor|player[- ]grade|relic|beat)\b", re.I), ConditionGrade.POOR),
]


def normalize_condition(text: str | None) -> ConditionGrade | None:
    """Return the best-match ConditionGrade for a free-text condition string, or None."""
    if not text:
        return None
    for pattern, grade in _PATTERNS:
        if pattern.search(text):
            return grade
    return None
