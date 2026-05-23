"""Reverb Price Guide scraper — DISABLED by default.

The Reverb Price Guide is a paid product and Reverb's Terms of Service
prohibit scraping. This module is gated behind the REVERB_SCRAPER_ENABLED=1
environment variable and exists for personal research use only.

For any public deployment, prefer the official Reverb API
(`gibson_price.ingest.reverb_api`) plus the Vintage Guitar Price Guide
seed CSV. This module raises at import time if the env var is unset, so
the public Streamlit app can never accidentally hit it.

If you set REVERB_SCRAPER_ENABLED=1, you accept responsibility for
compliance with Reverb's Terms of Service in your jurisdiction.
"""

from __future__ import annotations

import logging
import os
import time
from urllib.robotparser import RobotFileParser

import requests_cache
from bs4 import BeautifulSoup

from gibson_price.schema import GuitarListing

log = logging.getLogger(__name__)

if os.environ.get("REVERB_SCRAPER_ENABLED") != "1":
    raise RuntimeError(
        "reverb_scraper is disabled. Set REVERB_SCRAPER_ENABLED=1 to enable "
        "(personal research use only — review Reverb ToS)."
    )

BASE = "https://reverb.com"
PRICE_GUIDE_PATH = "/price-guide"
USER_AGENT = "gibson-price-research/0.1 (personal research; +github.com/JeremySNR)"
RATE_LIMIT_SECONDS = 2.0  # extra-polite

_session = requests_cache.CachedSession(
    cache_name=".cache/reverb_scrape",
    expire_after=60 * 60 * 24 * 7,
    allowable_methods=("GET",),
)
_session.headers.update({"User-Agent": USER_AGENT})


def _check_robots(path: str) -> bool:
    rp = RobotFileParser()
    rp.set_url(f"{BASE}/robots.txt")
    try:
        rp.read()
    except Exception as e:
        log.warning("Could not fetch robots.txt: %s", e)
        return False
    return rp.can_fetch(USER_AGENT, f"{BASE}{path}")


def scrape_price_guide_page(slug: str) -> list[GuitarListing]:
    """Scrape a single price-guide page (e.g. 'gibson-1965-j-45-natural')."""
    path = f"{PRICE_GUIDE_PATH}/{slug}"
    if not _check_robots(path):
        log.warning("robots.txt disallows %s — skipping", path)
        return []
    time.sleep(RATE_LIMIT_SECONDS)
    resp = _session.get(f"{BASE}{path}", timeout=20)
    if resp.status_code != 200:
        log.warning("Reverb scrape %s on %s", resp.status_code, path)
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    return _extract_listings(soup, slug)


def _extract_listings(soup: BeautifulSoup, slug: str) -> list[GuitarListing]:
    """Parse the price-guide page DOM. Selectors are documented but may break
    if Reverb redesigns; this is the inherent fragility of scraping."""
    listings: list[GuitarListing] = []
    cards = soup.select("[data-product-id], .price-guide-sale-row")
    for i, card in enumerate(cards):
        price_text = card.get("data-price") or (card.select_one(".sale-price") or {}).get_text("") if hasattr(card, "select_one") else ""
        try:
            price = float(str(price_text).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            continue
        listings.append(
            GuitarListing(
                source="reverb_scrape",
                source_listing_id=f"{slug}-{i:04d}",
                brand="Gibson",
                model_family="Unknown",
                price_usd=price,
                is_sold=True,
            )
        )
    return listings
