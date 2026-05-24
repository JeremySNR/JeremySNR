"""Parse free-text listing descriptions for originality and damage signals.

Designed to be aggressive on recall, conservative on precision — false positives
slightly underprice but false negatives (missing a known refinish) badly overprice.
The model uses these as inputs alongside any explicit booleans set by the loader.
"""

from __future__ import annotations

import contextlib
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

# Structural alterations — distinct from refinish/replaced-part; these change the instrument's identity.
_TOP_REPLACED = re.compile(r"\b(replac(?:ed|ement)|new|swapped)\s+top\b|\bre[- ]?topped\b|\btop\s+(?:graft|replac)", re.I)
_BACK_SIDES_REPLACED = re.compile(r"\b(replac(?:ed|ement)|new|swapped)\s+(?:back\s+(?:and|&)\s+sides|back/sides|sides)\b", re.I)
_NECK_REPLACED = re.compile(r"\b(replac(?:ed|ement)|new|donor)\s+neck\b|\bneck\s+graft\b", re.I)
_REBRACED = re.compile(r"\b(re[- ]?braced|new\s+bracing|replac(?:ed|ement)\s+bracing|bracing\s+(?:replaced|rebuilt|converted))\b", re.I)
_BODY_REPAIRED_MAJOR = re.compile(r"\b(major\s+body\s+(?:repair|work)|body\s+rebuilt|extensive\s+(?:body\s+)?repair|binding\s+(?:fully\s+)?(?:redone|replaced))\b", re.I)
_ELECTRIFIED = re.compile(r"\b(aftermarket|installed|added)\s+(?:pickup\s+system|preamp|electronics|under[- ]?saddle)\b|\bk&k\b|\bL\.R\.\s*Baggs\b|\bfishman\s+(?:matrix|infinity)\b", re.I)
_CUTAWAY_CONVERSION = re.compile(r"\b(converted\s+(?:to\s+)?cutaway|cutaway\s+conversion|added\s+cutaway)\b", re.I)
_FRANKENGUITAR = re.compile(r"\b(franken(?:guitar|stein)|parts(?:caster)?\s+(?:guitar|build)|composite\s+(?:instrument|guitar)|assembled\s+from\s+(?:multiple|donor))\b", re.I)
# Capture a year that follows a temporal preposition ("in 1968", "from 1968", "circa 1968").
# This avoids matching the guitar's manufacture year (which usually appears bare at the start
# of the title) and only fires when there's a temporal anchor — which is how dealers
# describe the era of a replacement component.
_REPLACEMENT_YEAR_NEAR_TOP = re.compile(
    r"\b(?:installed\s+in|added\s+in|replaced\s+in|re[- ]?topped\s+in|from|circa|c\.|around|~|in)\s+(19[2-9][0-9]|20[0-2][0-9])\b",
    re.I,
)


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
    # Structural alterations
    top_replaced: bool = False
    back_sides_replaced: bool = False
    neck_replaced: bool = False
    rebraced: bool = False
    body_repaired_major: bool = False
    electrified_aftermarket: bool = False
    converted_cutaway: bool = False
    frankenguitar: bool = False
    # Year-of-replacement guess from nearby text (None if not found)
    replacement_year_hint: int | None = None
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
        (_TOP_REPLACED, "top_replaced"),
        (_BACK_SIDES_REPLACED, "back_sides_replaced"),
        (_NECK_REPLACED, "neck_replaced"),
        (_REBRACED, "rebraced"),
        (_BODY_REPAIRED_MAJOR, "body_repaired_major"),
        (_ELECTRIFIED, "electrified_aftermarket"),
        (_CUTAWAY_CONVERSION, "converted_cutaway"),
        (_FRANKENGUITAR, "frankenguitar"),
    ]
    for pattern, attr in checks:
        match = pattern.search(text)
        if match:
            setattr(sig, attr, True)
            sig.matched_phrases.append(match.group(0))

    # If any structural alteration was detected, look for a replacement-year hint
    if any([sig.top_replaced, sig.back_sides_replaced, sig.neck_replaced, sig.rebraced]):
        m = _REPLACEMENT_YEAR_NEAR_TOP.search(text)
        if m:
            with contextlib.suppress(ValueError, TypeError):
                sig.replacement_year_hint = int(m.group(1))

    return sig
