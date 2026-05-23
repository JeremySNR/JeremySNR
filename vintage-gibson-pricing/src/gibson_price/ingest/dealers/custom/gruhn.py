"""Gruhn Guitars (guitars.com) — custom HTML parser.

Gruhn runs a long-lived custom CMS, not Shopify. Inventory pages are
paginated; each item has a title block, a price block, and a description.

NOTE: Selectors are documented from the current site layout. If Gruhn
redesigns, these break — that's the inherent fragility of HTML scraping.
The runner manifests will surface drift.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from gibson_price.features.condition import normalize_condition
from gibson_price.ingest.base import PolitenessConfig, make_session, polite_get
from gibson_price.ingest.title_parser import parse_title
from gibson_price.schema import GuitarListing

log = logging.getLogger(__name__)

BASE = "https://guitars.com"
INVENTORY_PATHS = ("/inventory", "/inventory/page/{page}")

CFG = PolitenessConfig(cache_name="gruhn", rate_limit_seconds=3.0)
_session = make_session(CFG)


def fetch(*, max_pages: int = 8, **_) -> list[GuitarListing]:
    out: list[GuitarListing] = []
    for page in range(1, max_pages + 1):
        path = "/inventory" if page == 1 else f"/inventory/page/{page}"
        resp = polite_get(_session, f"{BASE}{path}", CFG)
        if resp is None or resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        # Documented selectors. Will need maintenance.
        cards = soup.select(".inventory-item, .product-card, article.guitar")
        if not cards:
            break
        for card in cards:
            listing = _parse_card(card)
            if listing:
                out.append(listing)
    return out


def _parse_card(card) -> GuitarListing | None:
    title_el = card.select_one(".item-title, .product-title, h2 a, h3 a")
    price_el = card.select_one(".item-price, .product-price, .price")
    link_el = card.select_one("a[href*='/inventory/'], a[href*='/item/']")
    if not (title_el and price_el):
        return None
    title = title_el.get_text(" ", strip=True)
    price_text = price_el.get_text(strip=True).replace("$", "").replace(",", "")
    try:
        price_usd = float(price_text.split()[0])
    except (ValueError, IndexError):
        return None
    parsed = parse_title(title)
    if parsed.confidence < 0.4 or parsed.brand is None or parsed.model_family is None:
        return None
    href = link_el.get("href") if link_el else None
    url = f"{BASE}{href}" if href and href.startswith("/") else href
    desc_el = card.select_one(".item-description, .product-description, p")
    description = desc_el.get_text(" ", strip=True) if desc_el else ""
    cond = normalize_condition(description) or normalize_condition(title)

    return GuitarListing(
        source="dealer_custom",
        source_listing_id=f"gruhn:{href or title[:48]}",
        brand=parsed.brand,  # type: ignore[arg-type]
        model_family=parsed.model_family,
        year=parsed.year,
        condition_grade=cond,
        price_usd=price_usd,
        price_confidence="asking",
        is_sold=False,
        description=description[:2000],
        url=url,
        extraction_confidence=parsed.confidence,
    )
