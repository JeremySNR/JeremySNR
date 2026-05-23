"""CLI entry: pull listings from a chosen source and emit a JSONL file.

Usage:
    python scripts/ingest.py --source reverb_api --brand Gibson
    python scripts/ingest.py --source heritage --brand Gibson --model J-45
    python scripts/ingest.py --source vg_guide          # loads the committed seed CSV
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gibson_price.ingest import heritage_scraper, reverb_api, vg_price_guide  # noqa: E402
from gibson_price.schema import GuitarListing  # noqa: E402

log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True,
                        choices=["reverb_api", "heritage", "vg_guide", "reverb_scrape"])
    parser.add_argument("--brand", default="Gibson")
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "raw" / "out.jsonl")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    listings: list[GuitarListing] = []
    if args.source == "reverb_api":
        listings = reverb_api.fetch_listings(brand=args.brand, query=args.model, max_pages=args.max_pages)
    elif args.source == "heritage":
        listings = heritage_scraper.search_realized(brand=args.brand, model=args.model, max_pages=args.max_pages)
    elif args.source == "vg_guide":
        listings = vg_price_guide.load_seed(ROOT / "data" / "seed" / "gibson_acoustic_seed.csv")
    elif args.source == "reverb_scrape":
        from gibson_price.ingest import reverb_scraper  # noqa: F401  raises if disabled
        listings = []
        log.warning("reverb_scrape is interactive — see reverb_scraper.scrape_price_guide_page")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        for lst in listings:
            f.write(lst.model_dump_json() + "\n")
    log.info("Wrote %d listings to %s", len(listings), args.out)


if __name__ == "__main__":
    main()
