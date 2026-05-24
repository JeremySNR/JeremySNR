"""Load the seed CSV (Vintage Guitar Price Guide / dealer comps anchor) into GuitarListing records.

This is the primary day-one data source — it works with zero credentials and is
versioned in-repo, so the project is reproducible and demoable out of the box.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from gibson_price.schema import ConditionGrade, GuitarListing


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _parse_bool(s: str | None) -> bool:
    return str(s).strip() in {"1", "true", "True", "yes"}


def _parse_int(s: str | None) -> int | None:
    if not s:
        return None
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _parse_float(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def load_seed(path: str | Path) -> list[GuitarListing]:
    path = Path(path)
    out: list[GuitarListing] = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            cond = _parse_int(row.get("condition_grade"))
            out.append(
                GuitarListing(
                    source=row.get("source") or "vg_guide",  # type: ignore[arg-type]
                    source_listing_id=row["source_listing_id"],
                    brand=row["brand"],  # type: ignore[arg-type]
                    model_family=row["model_family"],
                    year=_parse_int(row.get("year")),
                    serial_number=row.get("serial_number") or None,
                    condition_grade=ConditionGrade(cond) if cond else None,
                    refinished=_parse_bool(row.get("refinished")),
                    headstock_repaired=_parse_bool(row.get("headstock_repaired")),
                    neck_reset=_parse_bool(row.get("neck_reset")),
                    refret=_parse_bool(row.get("refret")),
                    top_crack=_parse_bool(row.get("top_crack")),
                    side_crack=_parse_bool(row.get("side_crack")),
                    binding_shrinkage=_parse_bool(row.get("binding_shrinkage")),
                    replaced_tuners=_parse_bool(row.get("replaced_tuners")),
                    replaced_bridge=_parse_bool(row.get("replaced_bridge")),
                    replaced_pickup=_parse_bool(row.get("replaced_pickup")),
                    replaced_pickguard=_parse_bool(row.get("replaced_pickguard")),
                    top_replaced=_parse_bool(row.get("top_replaced")),
                    top_replacement_year=_parse_int(row.get("top_replacement_year")),
                    back_sides_replaced=_parse_bool(row.get("back_sides_replaced")),
                    back_sides_replacement_year=_parse_int(row.get("back_sides_replacement_year")),
                    neck_replaced=_parse_bool(row.get("neck_replaced")),
                    rebraced=_parse_bool(row.get("rebraced")),
                    body_repaired_major=_parse_bool(row.get("body_repaired_major")),
                    electrified_aftermarket=_parse_bool(row.get("electrified_aftermarket")),
                    converted_cutaway=_parse_bool(row.get("converted_cutaway")),
                    frankenguitar=_parse_bool(row.get("frankenguitar")),
                    has_original_case=_parse_bool(row.get("has_original_case")),
                    has_original_receipt=_parse_bool(row.get("has_original_receipt")),
                    has_pre_war_certification=_parse_bool(row.get("has_pre_war_certification")),
                    prior_famous_owner=_parse_bool(row.get("prior_famous_owner")),
                    is_sold=_parse_bool(row.get("is_sold")),
                    sold_date=_parse_date(row.get("sold_date")),
                    price_usd=_parse_float(row.get("price_usd")),
                    description=row.get("description") or None,
                )
            )
    return out
