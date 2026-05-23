"""Elderly Instruments (elderly.com) — custom CMS HTML parser.

Elderly's used/vintage section uses a custom CMS with rich structured fields
(serial numbers explicitly labelled, condition normalized to their own scale).
The parser opportunistically extracts the structured fields when present and
falls back to title-parsing otherwise.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from gibson_price.features.condition import normalize_condition
from gibson_price.ingest.base import PolitenessConfig, make_session, polite_get
from gibson_price.ingest.title_parser import parse_title
from gibson_price.schema import GuitarListing

log = logging.getLogger(__name__)

BASE = "https://www.elderly.com"
INVENTORY_PATH = "/collections/used-acoustic-guitars"

CFG = PolitenessConfig(cache_name="elderly", rate_limit_seconds=2.5)
_session = make_session(CFG)


def fetch(*, max_pages: int = 8, **_) -> list[GuitarListing]:
    out: list[GuitarListing] = []
    for page in range(1, max_pages + 1):
        url = f"{BASE}{INVENTORY_PATH}?page={page}"
        resp = polite_get(_session, url, CFG)
        if resp is None or resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".product-card, .grid__item, article.product")
        if not cards:
            break
        for card in cards:
            listing = _parse_card(card)
            if listing:
                out.append(listing)
    return out


def _serial_from_text(text: str) -> str | None:
    match = re.search(r"\b(?:serial|s/n)[: #]*([A-Z0-9-]{4,12})\b", text, re.I)
    return match.group(1) if match else None


def _parse_card(card) -> GuitarListing | None:
    title_el = card.select_one(".product-card__title, .product__title, h2 a")
    price_el = card.select_one(".product-card__price, .price__regular, .price")
    if not (title_el and price_el):
        return None
    title = title_el.get_text(" ", strip=True)
    price_text = price_el.get_text(strip=True).replace("$", "").replace(",", "")
    try:
        price_usd = float(re.split(r"\s|—|-", price_text)[0])
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
    serial = _serial_from_text(description) or _serial_from_text(title)

    return GuitarListing(
        source="dealer_custom",
        source_listing_id=f"elderly:{href or title[:48]}",
        brand=parsed.brand,  # type: ignore[arg-type]
        model_family=parsed.model_family,
        year=parsed.year,
        serial_number=serial,
        condition_grade=cond,
        price_usd=price_usd,
        price_confidence="asking",
        is_sold=False,
        description=description[:2000],
        url=url,
        extraction_confidence=parsed.confidence,
    )
