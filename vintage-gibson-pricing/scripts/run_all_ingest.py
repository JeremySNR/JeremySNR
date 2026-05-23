"""Orchestrator: pull from every enabled dealer + Wayback diff + Heritage.

Each source writes a JSONL of listings plus a manifest with timing, count,
and errors. The manifests are committable artefacts — a quick `cat data/raw/*.manifest.json`
shows which sources are healthy without re-running.

Usage:
    python scripts/run_all_ingest.py                    # all enabled
    python scripts/run_all_ingest.py --only carter_vintage,gruhn
    python scripts/run_all_ingest.py --skip-wayback
    python scripts/run_all_ingest.py --skip-heritage
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gibson_price.ingest import dealer_archive, heritage_scraper  # noqa: E402
from gibson_price.ingest.dealers import shopify  # noqa: E402
from gibson_price.ingest.dealers.registry import DealerConfig, enabled_dealers  # noqa: E402
from gibson_price.schema import GuitarListing  # noqa: E402

log = logging.getLogger(__name__)

RAW_DIR = ROOT / "data" / "raw"


@dataclass
class SourceManifest:
    source: str
    started_at: str
    finished_at: str = ""
    duration_seconds: float = 0.0
    listing_count: int = 0
    output_path: str = ""
    errors: list[str] = field(default_factory=list)


def _fetch_dealer(dealer: DealerConfig) -> list[GuitarListing]:
    if dealer.platform == "shopify":
        return shopify.fetch_products(
            dealer.url,
            dealer_name=dealer.name,
            brand_filter=dealer.brand_focus,
        )
    if dealer.platform == "custom":
        if not dealer.fetcher:
            raise ValueError(f"Custom dealer {dealer.name} missing `fetcher`")
        module_path, _, attr = dealer.fetcher.partition(":")
        module = importlib.import_module(module_path)
        return getattr(module, attr)()
    raise ValueError(f"Unknown platform {dealer.platform}")


def _write_jsonl(listings: list[GuitarListing], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for lst in listings:
            f.write(lst.model_dump_json() + "\n")


def _write_manifest(manifest: SourceManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(manifest), f, indent=2)


def _run_source(name: str, fn) -> SourceManifest:
    manifest = SourceManifest(
        source=name,
        started_at=datetime.now(UTC).isoformat(),
        output_path=str(RAW_DIR / f"{name}.jsonl"),
    )
    t0 = time.time()
    try:
        listings = fn()
        manifest.listing_count = len(listings)
        _write_jsonl(listings, RAW_DIR / f"{name}.jsonl")
    except Exception as e:
        manifest.errors.append(f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")
        log.warning("Source %s failed: %s", name, e)
    manifest.finished_at = datetime.now(UTC).isoformat()
    manifest.duration_seconds = round(time.time() - t0, 2)
    _write_manifest(manifest, RAW_DIR / f"{name}.manifest.json")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Comma-separated source names to run")
    parser.add_argument("--skip-wayback", action="store_true")
    parser.add_argument("--skip-heritage", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    only = set(args.only.split(",")) if args.only else None
    manifests: list[SourceManifest] = []

    for dealer in enabled_dealers():
        if only and dealer.name not in only:
            continue
        log.info("=== %s (%s) ===", dealer.name, dealer.platform)
        manifests.append(_run_source(dealer.name, lambda d=dealer: _fetch_dealer(d)))

    if not args.skip_heritage and (only is None or "heritage" in only):
        log.info("=== heritage ===")
        manifests.append(_run_source(
            "heritage",
            lambda: (
                heritage_scraper.search_realized(brand="Gibson", max_pages=5)
                + heritage_scraper.search_realized(brand="Martin", max_pages=3)
            ),
        ))

    if not args.skip_wayback and (only is None or "wayback" in only):
        log.info("=== wayback diff (sold inference) ===")
        manifests.append(_run_source("wayback", dealer_archive.ingest_all))

    log.info("\n=== Summary ===")
    for m in manifests:
        status = "ok" if not m.errors else "FAIL"
        log.info("%-22s %-6s %5d listings  %6.1fs", m.source, status, m.listing_count, m.duration_seconds)


if __name__ == "__main__":
    main()
