"""Reverb official API client — active listings (asking prices).

Auth: set REVERB_API_TOKEN in the environment. Get one from
https://www.reverb-api.com/. Asking-price data only; the model
learns a discount factor vs sold prices from the other sources.

API surface used:
    GET /api/listings?query=...&category_slug=acoustic-guitars&product_brand=Gibson
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date

import requests
import requests_cache

from gibson_price.schema import GuitarListing

log = logging.getLogger(__name__)

REVERB_BASE = "https://api.reverb.com/api"
RATE_LIMIT_SECONDS = 0.5  # 2 req/sec polite ceiling
DEFAULT_TIMEOUT = 20


def _session() -> requests.Session:
    session = requests_cache.CachedSession(
        cache_name=".cache/reverb_api",
        expire_after=60 * 60 * 24,
        allowable_methods=("GET",),
    )
    token = os.environ.get("REVERB_API_TOKEN")
    if not token:
        raise RuntimeError(
            "REVERB_API_TOKEN env var not set. Get a token at https://www.reverb-api.com/."
        )
    session.headers.update({
        "Accept": "application/hal+json",
        "Accept-Version": "3.0",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    return session


def fetch_listings(
    *,
    brand: str = "Gibson",
    query: str | None = None,
    per_page: int = 50,
    max_pages: int = 10,
) -> list[GuitarListing]:
    """Pull active Reverb acoustic-guitar listings for a brand. Asking prices only."""
    session = _session()
    results: list[GuitarListing] = []
    for page in range(1, max_pages + 1):
        params = {
            "category_slug": "acoustic-guitars",
            "product_brand": brand,
            "per_page": per_page,
            "page": page,
        }
        if query:
            params["query"] = query
        resp = session.get(f"{REVERB_BASE}/listings", params=params, timeout=DEFAULT_TIMEOUT)
        if resp.status_code != 200:
            log.warning("Reverb API %s on page %d", resp.status_code, page)
            break
        payload = resp.json()
        listings = payload.get("listings", [])
        if not listings:
            break
        for raw in listings:
            results.append(_to_listing(raw, brand))
        time.sleep(RATE_LIMIT_SECONDS)
    return results


def _to_listing(raw: dict, brand: str) -> GuitarListing:
    price = raw.get("buyer_price", {}).get("amount") or raw.get("price", {}).get("amount")
    try:
        price_usd = float(price) if price else None
    except (ValueError, TypeError):
        price_usd = None

    return GuitarListing(
        source="reverb_api",
        source_listing_id=str(raw.get("id") or raw.get("slug") or ""),
        brand=brand,  # type: ignore[arg-type]
        model_family=str(raw.get("model") or "Unknown"),
        year=_safe_year(raw.get("year")),
        condition_grade=None,  # populated downstream via features.condition.normalize_condition
        price_usd=price_usd,
        is_sold=False,
        listing_date=date.today(),
        description=raw.get("description"),
        url=raw.get("_links", {}).get("web", {}).get("href"),
    )


def _safe_year(val: object) -> int | None:
    try:
        y = int(str(val).strip()[:4])
        return y if 1900 <= y <= 2099 else None
    except (ValueError, TypeError, AttributeError):
        return None
