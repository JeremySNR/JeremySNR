"""Wayback-Machine-driven sold-state inference for dealer inventories.

For dealers in the registry, this module pulls the Wayback CDX timemap for the
dealer's inventory page, fetches a chronological sequence of snapshots, extracts
the set of product IDs visible in each, and runs `wayback.infer_sold_from_history`
to identify items that disappeared and stayed gone — a strong sold-state signal.

Each "presumed sold" record gets `is_sold=True, price_confidence="inferred"`
so the model can weight it appropriately versus actual sold prices from
Heritage Auctions.

Coverage is best for high-traffic dealers (Carter, Norman's, Gruhn) where the
Wayback Machine crawls weekly. Smaller dealers may have sparse snapshots,
limiting inference quality.
"""

from __future__ import annotations

import contextlib
import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from gibson_price.ingest import wayback
from gibson_price.ingest.dealers.registry import DealerConfig, enabled_dealers
from gibson_price.ingest.title_parser import parse_title
from gibson_price.schema import GuitarListing

log = logging.getLogger(__name__)


@dataclass
class ParsedSnapshotItem:
    """A product visible in a single Wayback snapshot of a dealer's inventory page."""

    stable_id: str
    title: str
    price_usd: float | None


def _parse_snapshot_html(html: str) -> list[ParsedSnapshotItem]:
    """Best-effort generic extractor across dealer site shapes.

    We look for any anchor whose href contains /product/ or /products/ or
    /inventory/ — these are stable per-dealer-CMS patterns that survive
    most theme changes. Price extraction is fuzzy but acceptable for
    diff-based sold inference, where the exact price is the last-seen
    asking price, not a precise sold figure.
    """
    soup = BeautifulSoup(html, "html.parser")
    items: list[ParsedSnapshotItem] = []
    for anchor in soup.select("a[href*='/products/'], a[href*='/product/'], a[href*='/inventory/'], a[href*='/item/']"):
        href = anchor.get("href") or ""
        # Stable ID: just the slug after the product path
        match = re.search(r"/(?:products|product|inventory|item)/([^/?#]+)", href)
        if not match:
            continue
        stable_id = match.group(1)
        title = anchor.get_text(" ", strip=True) or anchor.get("title") or ""
        # Price is whatever number-looking text is nearby — best effort
        parent = anchor.find_parent(["div", "li", "article"]) or anchor
        price_text = parent.get_text(" ", strip=True)
        match_price = re.search(r"\$([0-9,]{3,8})(?!\d)", price_text)
        price_usd: float | None = None
        if match_price:
            with contextlib.suppress(ValueError):
                price_usd = float(match_price.group(1).replace(",", ""))
        items.append(ParsedSnapshotItem(stable_id=stable_id, title=title, price_usd=price_usd))
    return items


def _resolve_inventory_url(dealer: DealerConfig) -> str:
    base = dealer.url.rstrip("/")
    if dealer.inventory_paths:
        return f"{base}{dealer.inventory_paths[0]}"
    return base


def ingest_dealer_history(
    dealer: DealerConfig,
    *,
    max_snapshots: int = 8,
    min_consecutive_absences: int = 2,
) -> list[GuitarListing]:
    """Pull dealer's Wayback history, infer sold items, return GuitarListings."""
    inventory_url = _resolve_inventory_url(dealer)
    snapshots = wayback.list_snapshots(inventory_url, limit=max_snapshots)
    if len(snapshots) < min_consecutive_absences + 1:
        log.info("Too few snapshots (%d) for %s — skipping", len(snapshots), dealer.name)
        return []

    # For each snapshot, fetch and parse
    history: list[tuple[str, set[str]]] = []
    last_seen_meta: dict[str, ParsedSnapshotItem] = {}
    for snap in snapshots:
        html = wayback.fetch_snapshot_html(snap)
        if html is None:
            continue
        items = _parse_snapshot_html(html)
        ids = {it.stable_id for it in items}
        history.append((snap.timestamp, ids))
        for it in items:
            # Record the most recent metadata for each stable_id
            last_seen_meta[it.stable_id] = it

    presumed_sold = wayback.infer_sold_from_history(
        history, min_consecutive_absences=min_consecutive_absences
    )
    log.info("%s: %d snapshots, %d presumed-sold IDs", dealer.name, len(history), len(presumed_sold))

    out: list[GuitarListing] = []
    for stable_id in presumed_sold:
        meta = last_seen_meta.get(stable_id)
        if not meta or not meta.title:
            continue
        parsed = parse_title(meta.title)
        if parsed.confidence < 0.4 or parsed.brand is None or parsed.model_family is None:
            continue
        out.append(GuitarListing(
            source="dealer_archive",
            source_listing_id=f"{dealer.name}:wayback:{stable_id}",
            brand=parsed.brand,  # type: ignore[arg-type]
            model_family=parsed.model_family,
            year=parsed.year,
            price_usd=meta.price_usd,
            price_confidence="inferred",
            is_sold=True,
            description=f"[wayback-inferred sold from {dealer.name}] {meta.title}",
            extraction_confidence=parsed.confidence,
        ))
    return out


def ingest_all() -> list[GuitarListing]:
    """Run Wayback inference across every enabled dealer in the registry."""
    out: list[GuitarListing] = []
    for dealer in enabled_dealers():
        try:
            out.extend(ingest_dealer_history(dealer))
        except Exception as e:
            log.warning("Wayback ingest for %s failed: %s", dealer.name, e)
    return out
