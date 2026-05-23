"""Feature matrix assembly.

Takes a list of GuitarListing records (from any ingest source) and turns them
into a pandas DataFrame whose columns match `schema.ALL_FEATURES`, plus a
`price_usd` target column. Applies domain defaults so missing fields don't
collapse to a useless "unknown" bucket.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from gibson_price.features.gibson_serial import year_from_listing
from gibson_price.features.originality import parse_description
from gibson_price.features.tonewood import canon_back_sides, canon_top
from gibson_price.schema import ALL_FEATURES, ConditionGrade, GuitarListing

# Body shape inferred from model family
BODY_SHAPE_BY_MODEL: dict[str, str] = {
    "J-45": "Round-Shoulder Dreadnought",
    "J-50": "Round-Shoulder Dreadnought",
    "Southern Jumbo": "Round-Shoulder Dreadnought",
    "Country Western": "Round-Shoulder Dreadnought",
    "Hummingbird": "Square-Shoulder Dreadnought",
    "Dove": "Square-Shoulder Dreadnought",
    "J-160E": "Round-Shoulder Dreadnought",
    "J-200": "Super Jumbo",
    "SJ-200": "Super Jumbo",
    "Advanced Jumbo": "Round-Shoulder Dreadnought",
    "L-00": "Small Body",
    "L-1": "Small Body",
    "L-2": "Small Body",
    "Nick Lucas": "Small Body",
    "LG-0": "Small Body",
    "LG-1": "Small Body",
    "LG-2": "Small Body",
    "LG-3": "Small Body",
    "B-25": "Small Body",
    "Everly Brothers": "Small Body",
    "D-18": "Dreadnought",
    "D-21": "Dreadnought",
    "D-28": "Dreadnought",
    "D-35": "Dreadnought",
    "D-41": "Dreadnought",
    "D-45": "Dreadnought",
    "000-18": "Auditorium",
    "000-28": "Auditorium",
    "OM-28": "Orchestra Model",
    "OM-45": "Orchestra Model",
    "00-17": "Grand Concert",
    "F-50": "Jumbo",
    "F-30": "Folk",
    "D-40": "Dreadnought",
    "D-50": "Dreadnought",
    "F-512": "Jumbo 12-string",
    "F-412": "Jumbo 12-string",
    "Rancher": "Jumbo",
    "Sun Valley": "Dreadnought",
    "Synchromatic": "Archtop",
}


def era_segment(year: int) -> str:
    if year < 1942:
        return "pre_war"
    if year < 1965:
        return "golden"
    if year < 1985:
        return "transition"
    return "modern"


def gibson_factory(year: int) -> str:
    if year < 1984:
        return "Kalamazoo"
    if year < 1989:
        return "Nashville"
    return "Bozeman"


def martin_factory(_year: int) -> str:
    return "Nazareth"


def factory_for(brand: str, year: int) -> str:
    if brand == "Gibson":
        return gibson_factory(year)
    if brand == "Martin":
        return martin_factory(year)
    if brand == "Guild":
        return "Westerly" if year < 2001 else "Tacoma"
    return "Unknown"


def bracing_pattern_for(brand: str, model_family: str, year: int) -> tuple[str, int]:
    """Return (pattern, scalloped_bool_as_int).

    Gibson scalloped bracing was used pre-WWII and reintroduced on some reissues post-2000.
    The "1955 cliff" refers to the loss of light scalloping on some models.
    Martin scalloped through 1944, then non-scalloped, scalloped reissues from 1976 onward.
    """
    if brand == "Gibson":
        if year < 1945:
            return ("X-brace", 1)
        if year < 1955:
            return ("X-brace", 1)  # tapered, lightly scalloped
        return ("X-brace", 0)
    if brand == "Martin":
        if year < 1945:
            return ("X-brace", 1)
        if year < 1976:
            return ("X-brace", 0)
        return ("X-brace", 1)  # scalloped reissues from HD-28 onward
    return ("X-brace", 0)


def bridge_type_for(brand: str, model_family: str, year: int) -> str:
    """1961-1969 Gibson era had adjustable ceramic saddles, some plastic bridges
    on early-60s J-45s. These are material deductions in the model."""
    if brand == "Gibson" and 1961 <= year <= 1969:
        return "Adjustable Ceramic"
    return "Rosewood Pin"


def tuner_type_for(brand: str, year: int) -> str:
    if brand == "Gibson":
        if year < 1955:
            return "Kluson Single-Line"
        if year < 1965:
            return "Kluson Double-Line"
        return "Modern Sealed"
    if brand == "Martin":
        return "Waverly" if year < 1965 else "Modern Sealed"
    return "Modern Sealed"


def hide_glue_for(brand: str, year: int) -> int:
    """Gibson used hide glue through ~1965, switched to PVA, then reintroduced
    on some Bozeman reissues from ~2003 (e.g., 1942 Banner J-45 reissue)."""
    if brand == "Gibson" and year < 1965:
        return 1
    if brand == "Martin" and year < 1968:
        return 1
    return 0


def _listing_to_row(listing: GuitarListing, sold_year_default: int) -> dict[str, object] | None:
    year = year_from_listing(listing.serial_number, listing.year)
    if not year:
        return None
    if listing.price_usd is None or listing.price_usd <= 0:
        return None

    parsed = parse_description(listing.description)

    refinished = listing.refinished or parsed.refinished
    headstock_repaired = listing.headstock_repaired or parsed.headstock_repaired
    neck_reset = listing.neck_reset or parsed.neck_reset
    refret = listing.refret or parsed.refret
    top_crack = listing.top_crack or parsed.top_crack
    side_crack = listing.side_crack or parsed.side_crack
    binding_shrinkage = listing.binding_shrinkage or parsed.binding_shrinkage
    replaced_tuners = listing.replaced_tuners or parsed.replaced_tuners
    replaced_bridge = listing.replaced_bridge or parsed.replaced_bridge
    replaced_pickup = listing.replaced_pickup or parsed.replaced_pickup
    replaced_pickguard = listing.replaced_pickguard or parsed.replaced_pickguard
    has_original_case = listing.has_original_case or parsed.has_original_case
    has_original_receipt = listing.has_original_receipt or parsed.has_original_receipt

    condition = listing.condition_grade or ConditionGrade.VERY_GOOD
    bracing_pattern, scalloped = bracing_pattern_for(listing.brand, listing.model_family, year)
    sold_year = (listing.sold_date or listing.listing_date or date(sold_year_default, 1, 1)).year

    row = {
        "brand": listing.brand,
        "model_family": listing.model_family,
        "year": year,
        "era_segment": era_segment(year),
        "factory": listing.factory or factory_for(listing.brand, year),
        "body_shape": BODY_SHAPE_BY_MODEL.get(listing.model_family, "Unknown"),
        "top_wood": canon_top(listing.top_wood, year),
        "back_sides_wood": canon_back_sides(listing.back_sides_wood, listing.model_family, year),
        "bracing_pattern": listing.bracing_pattern or bracing_pattern,
        "bracing_scalloped": int(listing.bracing_scalloped) if listing.bracing_scalloped is not None else scalloped,
        "bridge_type": listing.bridge_type or bridge_type_for(listing.brand, listing.model_family, year),
        "tuner_type": listing.tuner_type or tuner_type_for(listing.brand, year),
        "hide_glue_construction": int(listing.hide_glue_construction) if listing.hide_glue_construction is not None else hide_glue_for(listing.brand, year),
        "finish": listing.finish or "Sunburst",
        "sunburst_pattern": listing.sunburst_pattern or "Tobacco",
        "condition_grade": int(condition),
        "headstock_repaired": int(headstock_repaired),
        "neck_reset": int(neck_reset),
        "refret": int(refret),
        "top_crack": int(top_crack),
        "side_crack": int(side_crack),
        "binding_shrinkage": int(binding_shrinkage),
        "refinished": int(refinished),
        "replaced_tuners": int(replaced_tuners),
        "replaced_bridge": int(replaced_bridge),
        "replaced_pickup": int(replaced_pickup),
        "replaced_pickguard": int(replaced_pickguard),
        "has_original_case": int(has_original_case),
        "has_original_receipt": int(has_original_receipt),
        "has_pre_war_certification": int(listing.has_pre_war_certification),
        "prior_famous_owner": int(listing.prior_famous_owner),
        "source": listing.source,
        "sold_year": sold_year,
        "price_usd": float(listing.price_usd),
    }
    return row


def build_feature_frame(
    listings: list[GuitarListing],
    *,
    sold_year_default: int = 2024,
) -> pd.DataFrame:
    """Convert a list of GuitarListing to a model-ready DataFrame.

    Drops rows missing required fields (year, price). Returns columns:
    all features in `ALL_FEATURES` order + `price_usd` target.
    """
    rows = [
        r for r in (_listing_to_row(lst, sold_year_default) for lst in listings) if r is not None
    ]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    ordered = [*ALL_FEATURES, "price_usd"]
    return df[ordered]
