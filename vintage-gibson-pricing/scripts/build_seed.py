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


def main() -> None:
    with open(RANGES_YAML) as f:
        specs = yaml.safe_load(f)

    all_rows = []
    for spec in specs:
        all_rows.extend(expand_rows(spec))

    SEED_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(all_rows[0].keys())
    with open(SEED_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} rows to {SEED_CSV}")


if __name__ == "__main__":
    main()
