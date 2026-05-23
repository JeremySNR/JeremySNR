"""Heritage Auctions vintage-guitar archive scraper.

Heritage's auction-archive pages are publicly indexed and crawlable; this
loader respects robots.txt and rate-limits politely. Heritage's auction
results are the highest-quality signal for the premium tier of vintage
acoustics (pre-war D-45s, banner J-45s, etc.).

Department slug: vintage-guitars-and-musical-instruments
"""

from __future__ import annotations

import logging
import time
from datetime import date
from urllib.robotparser import RobotFileParser

import requests_cache
from bs4 import BeautifulSoup

from gibson_price.schema import GuitarListing

log = logging.getLogger(__name__)

BASE = "https://entertainment.ha.com"
SEARCH_PATH = "/c/search-results.zx"
USER_AGENT = "gibson-price-research/0.1 (personal research; +github.com/JeremySNR)"
RATE_LIMIT_SECONDS = 2.5

_session = requests_cache.CachedSession(
    cache_name=".cache/heritage",
    expire_after=60 * 60 * 24 * 30,
    allowable_methods=("GET",),
)
_session.headers.update({"User-Agent": USER_AGENT})


def _check_robots(path: str) -> bool:
    rp = RobotFileParser()
    rp.set_url(f"{BASE}/robots.txt")
    try:
        rp.read()
    except Exception as e:
        log.warning("Could not fetch Heritage robots.txt: %s", e)
        return False
    return rp.can_fetch(USER_AGENT, f"{BASE}{path}")


def search_realized(
    *,
    brand: str = "Gibson",
    model: str | None = None,
    max_pages: int = 5,
) -> list[GuitarListing]:
    """Search Heritage's realized-price archive for a brand/model."""
    if not _check_robots(SEARCH_PATH):
        log.warning("Heritage robots.txt disallows %s", SEARCH_PATH)
        return []

    out: list[GuitarListing] = []
    query = brand if not model else f"{brand} {model}"
    for page in range(1, max_pages + 1):
        params = {
            "type": "prices_realized_summary",
            "Ntt": query,
            "dept": "Vintage Guitars and Musical Instruments",
            "Nao": (page - 1) * 50,
        }
        time.sleep(RATE_LIMIT_SECONDS)
        resp = _session.get(f"{BASE}{SEARCH_PATH}", params=params, timeout=30)
        if resp.status_code != 200:
            log.warning("Heritage %s on page %d", resp.status_code, page)
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("tr.lot-row, .lot-summary, [data-lot-id]")
        if not rows:
            break
        for row in rows:
            listing = _parse_row(row, brand)
            if listing:
                out.append(listing)
    return out


def _parse_row(row, brand: str) -> GuitarListing | None:
    """Parse a single auction-result row. Selectors based on current Heritage layout;
    will need updating if the site redesigns."""
    title_el = row.select_one(".lot-title, a.lot-link")
    price_el = row.select_one(".realized-price, .price")
    if not (title_el and price_el):
        return None

    title = title_el.get_text(" ", strip=True)
    price_text = price_el.get_text(strip=True).replace("$", "").replace(",", "")
    try:
        price_usd = float(price_text.split()[0])
    except (ValueError, IndexError):
        return None

    lot_id = row.get("data-lot-id") or title[:32]
    return GuitarListing(
        source="heritage",
        source_listing_id=str(lot_id),
        brand=brand,  # type: ignore[arg-type]
        model_family=_infer_model(title),
        year=_infer_year(title),
        price_usd=price_usd,
        is_sold=True,
        sold_date=date.today(),
        description=title,
    )


def _infer_model(title: str) -> str:
    upper = title.upper()
    for candidate in ["J-45", "J-50", "SJ-200", "J-200", "HUMMINGBIRD", "DOVE",
                      "SOUTHERN JUMBO", "L-00", "LG-2", "D-28", "D-18", "D-45",
                      "000-28", "000-18", "ADVANCED JUMBO"]:
        if candidate in upper:
            return candidate.title().replace("Sj-200", "SJ-200").replace("J-", "J-").replace("L-00", "L-00")
    return "Unknown"


def _infer_year(title: str) -> int | None:
    import re

    match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", title)
    return int(match.group(1)) if match else None
