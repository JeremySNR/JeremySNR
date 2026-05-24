"""Generate the seed CSV from a compact YAML of price-guide ranges.

Each row in the YAML defines a (brand, model_family, year_range, condition_range, price_range)
tuple. The script expands these into individual rows by sampling within the ranges,
producing realistic-looking listing records that match published Vintage Guitar Price Guide
bands and dealer comps.

Run from the project root:
    python scripts/build_seed.py

Source basis for ranges:
  - Vintage Guitar Price Guide (annual edition)
  - Gruhn's Guide to Vintage Guitars
  - Joe's Vintage Guitars and Carter Vintage published comps
  - Heritage Auctions realized prices
  - Reverb Price Guide public ranges
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RANGES_YAML = ROOT / "data" / "seed" / "price_ranges.yaml"
AUG_YAML = ROOT / "data" / "seed" / "synthetic_augmentation_rules.yaml"
SEED_CSV = ROOT / "data" / "seed" / "gibson_acoustic_seed.csv"

random.seed(42)


def expand_rows(spec: dict) -> list[dict]:
    """Expand a single YAML range spec into individual listing rows."""
    rows = []
    brand = spec["brand"]
    model = spec["model_family"]
    year_lo, year_hi = spec["year_range"]
    cond_lo, cond_hi = spec["condition_range"]
    price_lo, price_hi = spec["price_range"]
    n = spec.get("count", 8)
    refin_share = spec.get("refin_share", 0.10)
    case_share = spec.get("case_share", 0.55)
    refin_discount = spec.get("refin_discount", 0.30)
    notes = spec.get("notes", "")

    for i in range(n):
        year = random.randint(year_lo, year_hi)
        condition = random.randint(cond_lo, cond_hi)
        base = random.uniform(price_lo, price_hi)
        refinished = random.random() < refin_share
        has_case = random.random() < case_share
        headstock_repaired = random.random() < 0.06
        neck_reset = random.random() < 0.20
        refret = random.random() < 0.18
        replaced_tuners = random.random() < 0.12
        replaced_bridge = random.random() < 0.05
        top_crack = random.random() < 0.08

        price = base
        if refinished:
            price *= 1 - refin_discount
        if headstock_repaired:
            price *= 0.55
        if replaced_bridge:
            price *= 0.85
        if replaced_tuners:
            price *= 0.95
        if refret:
            price *= 0.93
        if top_crack:
            price *= 0.88
        if has_case:
            price *= 1.03

        sold_offset_days = random.randint(0, 365 * 3)
        sold_date = date(2024, 6, 1) - timedelta(days=sold_offset_days)

        rows.append({
            "source": "vg_guide",
            "source_listing_id": f"{brand[:3].upper()}-{model.replace(' ', '')}-{year}-{i:03d}",
            "brand": brand,
            "model_family": model,
            "year": year,
            "serial_number": "",
            "condition_grade": condition,
            "refinished": int(refinished),
            "headstock_repaired": int(headstock_repaired),
            "neck_reset": int(neck_reset),
            "refret": int(refret),
            "top_crack": int(top_crack),
            "side_crack": 0,
            "binding_shrinkage": int(random.random() < 0.25),
            "replaced_tuners": int(replaced_tuners),
            "replaced_bridge": int(replaced_bridge),
            "replaced_pickup": 0,
            "replaced_pickguard": 0,
            "top_replaced": 0,
            "top_replacement_year": "",
            "back_sides_replaced": 0,
            "back_sides_replacement_year": "",
            "neck_replaced": 0,
            "rebraced": 0,
            "body_repaired_major": 0,
            "electrified_aftermarket": 0,
            "converted_cutaway": 0,
            "frankenguitar": 0,
            "has_original_case": int(has_case),
            "has_original_receipt": int(random.random() < 0.08),
            "has_pre_war_certification": int(brand == "Gibson" and year < 1942 and random.random() < 0.35),
            "prior_famous_owner": 0,
            "is_sold": True,
            "sold_date": sold_date.isoformat(),
            "price_usd": round(price, -1),
            "description": notes,
        })
    return rows


# Compound structural-modification variants the regular expand_rows won't produce.
# Sampled across the strongest priors so the model has training examples — the user's
# question ("what if a 40s guitar was retopped in the 60s") is the canonical case here.
STRUCTURAL_SCENARIOS = [
    # (label, alteration_flags_to_set, replacement_year_offset_or_None, multiplier)
    ("retop_modern_repro", {"top_replaced": 1}, +30, 0.50),
    ("retop_period_correct", {"top_replaced": 1}, +5, 0.65),       # within a decade, less damage
    ("retop_modern_generic", {"top_replaced": 1}, +50, 0.40),
    ("neck_replaced", {"neck_replaced": 1}, None, 0.40),
    ("rebraced_to_non_scalloped", {"rebraced": 1}, None, 0.65),
    ("body_repaired_major", {"body_repaired_major": 1}, None, 0.78),
    ("electrified", {"electrified_aftermarket": 1}, None, 0.92),
    ("cutaway_conversion", {"converted_cutaway": 1}, None, 0.62),
    ("frankenguitar", {"frankenguitar": 1, "neck_replaced": 1, "refinished": 1}, None, 0.30),
    ("retop_and_refin", {"top_replaced": 1, "refinished": 1}, +20, 0.32),
    ("back_sides_replaced", {"back_sides_replaced": 1}, None, 0.43),
]


def generate_structural_variants(base_rows: list[dict], per_row: float = 0.05) -> list[dict]:
    """For a random sample of base rows, generate structural-mod variants.

    `per_row` = expected number of variants per base row (Poisson rate). Defaults
    to ~5%, so a 684-row base yields ~30-40 structural variants spread across
    the scenario library.
    """
    variants = []
    for base in base_rows:
        if random.random() > per_row:
            continue
        scenario = random.choice(STRUCTURAL_SCENARIOS)
        label, flags, year_offset, multiplier = scenario

        base_year = int(base["year"])
        variant = dict(base)
        variant["source_listing_id"] = f"{base['source_listing_id']}-{label}"
        variant["price_usd"] = max(round(base["price_usd"] * multiplier, -1), 500)
        variant["description"] = f"{base.get('description', '')} [synthetic {label}]"
        # Apply the structural flags
        for flag, val in flags.items():
            variant[flag] = val
        if "top_replaced" in flags and year_offset is not None:
            variant["top_replacement_year"] = base_year + year_offset
        variants.append(variant)
    return variants


def main() -> None:
    with open(RANGES_YAML) as f:
        specs = yaml.safe_load(f)
    # AUG_YAML is loaded by the model's synthetic augmentation pass; not used here.
    _ = AUG_YAML

    all_rows = []
    for spec in specs:
        all_rows.extend(expand_rows(spec))

    # Add structural-mod variants on top of the base rows. These teach the model
    # to handle the "what if a 40s guitar was retopped in the 60s" case.
    structural = generate_structural_variants(all_rows, per_row=0.10)
    all_rows.extend(structural)

    SEED_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(all_rows[0].keys())
    with open(SEED_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} rows to {SEED_CSV}  ({len(structural)} structural-mod variants)")


if __name__ == "__main__":
    main()
