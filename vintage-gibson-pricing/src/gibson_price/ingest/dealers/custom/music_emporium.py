"""The Music Emporium (themusicemporium.com) — Magento-based HTML parser."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from gibson_price.features.condition import normalize_condition
from gibson_price.ingest.base import PolitenessConfig, make_session, polite_get
from gibson_price.ingest.title_parser import parse_title
from gibson_price.schema import GuitarListing

log = logging.getLogger(__name__)

BASE = "https://www.themusicemporium.com"
INVENTORY_PATH = "/collections/acoustic-guitars"

CFG = PolitenessConfig(cache_name="music_emporium", rate_limit_seconds=2.5)
_session = make_session(CFG)


def fetch(*, max_pages: int = 8, **_) -> list[GuitarListing]:
    out: list[GuitarListing] = []
    for page in range(1, max_pages + 1):
        resp = polite_get(_session, f"{BASE}{INVENTORY_PATH}?page={page}", CFG)
        if resp is None or resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".product-card, .product-grid-item, li.grid__item")
        if not cards:
            break
        for card in cards:
            listing = _parse_card(card)
            if listing:
                out.append(listing)
    return out


def _parse_card(card) -> GuitarListing | None:
    title_el = card.select_one("h3 a, .product-card__title, .product-title")
    price_el = card.select_one(".product-card__price, .price, .product__price")
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

    href_el = card.select_one("a[href*='/products/']")
    href = href_el.get("href") if href_el else None
    url = f"{BASE}{href}" if href and href.startswith("/") else href
    desc_el = card.select_one(".product-card__description, .product-meta")
    description = desc_el.get_text(" ", strip=True) if desc_el else ""
    cond = normalize_condition(description) or normalize_condition(title)

    return GuitarListing(
        source="dealer_custom",
        source_listing_id=f"music_emporium:{href or title[:48]}",
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
