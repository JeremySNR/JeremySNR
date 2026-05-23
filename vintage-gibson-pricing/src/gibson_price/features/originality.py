"""Parse free-text listing descriptions for originality and damage signals.

Designed to be aggressive on recall, conservative on precision — false positives
slightly underprice but false negatives (missing a known refinish) badly overprice.
The model uses these as inputs alongside any explicit booleans set by the loader.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_REFIN = re.compile(r"\b(refin(ish(ed)?|)|over[- ]?spray|stripped\s+(and\s+)?repainted)\b", re.I)
_HEADSTOCK = re.compile(r"\b(head\s*stock|headstock)\s*(break|crack|repair)|broken\s+head\s*stock\b", re.I)
_NECK_RESET = re.compile(r"\bneck\s*reset\b", re.I)
_REFRET = re.compile(r"\b(refret(ted|)|new\s+frets)\b", re.I)
_TOP_CRACK = re.compile(r"\btop\s*crack|crack(ed)?\s+top|pickguard\s+crack\b", re.I)
_SIDE_CRACK = re.compile(r"\bside\s*crack|crack(ed)?\s+side\b", re.I)
_BINDING = re.compile(r"\bbinding\s*(shrinkage|crack|loose|missing)\b", re.I)
_TUNERS = re.compile(r"\b(replaced|new|grover|gotoh|repro)\s+tuners?\b", re.I)
_BRIDGE = re.compile(r"\b(replaced|new|repro|reproduction)\s+bridge\b", re.I)
_PICKUP = re.compile(r"\b(added|installed|aftermarket|replaced)\s+pickup\b", re.I)
_PICKGUARD = re.compile(r"\b(replaced|new|repro)\s+pickguard\b", re.I)
_CASE = re.compile(r"\b(original|original\s+brown|chipboard|lifton|geib|hard\s*shell)\s+case\b", re.I)
_RECEIPT = re.compile(r"\b(original\s+receipt|sales\s+receipt|hang\s*tag|warranty\s+card|case\s+candy)\b", re.I)


@dataclass
class OriginalitySignals:
    refinished: bool = False
    headstock_repaired: bool = False
    neck_reset: bool = False
    refret: bool = False
    top_crack: bool = False
    side_crack: bool = False
    binding_shrinkage: bool = False
    replaced_tuners: bool = False
    replaced_bridge: bool = False
    replaced_pickup: bool = False
    replaced_pickguard: bool = False
    has_original_case: bool = False
    has_original_receipt: bool = False
    matched_phrases: list[str] = field(default_factory=list)


def parse_description(text: str | None) -> OriginalitySignals:
    sig = OriginalitySignals()
    if not text:
        return sig
    checks: list[tuple[re.Pattern[str], str]] = [
        (_REFIN, "refinished"),
        (_HEADSTOCK, "headstock_repaired"),
        (_NECK_RESET, "neck_reset"),
        (_REFRET, "refret"),
        (_TOP_CRACK, "top_crack"),
        (_SIDE_CRACK, "side_crack"),
        (_BINDING, "binding_shrinkage"),
        (_TUNERS, "replaced_tuners"),
        (_BRIDGE, "replaced_bridge"),
        (_PICKUP, "replaced_pickup"),
        (_PICKGUARD, "replaced_pickguard"),
        (_CASE, "has_original_case"),
        (_RECEIPT, "has_original_receipt"),
    ]
    for pattern, attr in checks:
        match = pattern.search(text)
        if match:
            setattr(sig, attr, True)
            sig.matched_phrases.append(match.group(0))
    return sig
