"""Wayback Machine sourced dealer snapshots.

Dealers like Gruhn Guitars, Carter Vintage Guitars, Elderly Instruments, and
Folkway Music maintain catalogs with high-quality detailed listings, but sold
items disappear from the live site. The Wayback Machine indexes historical
snapshots, and pulling from there is legitimate use.

Inference logic: an item present in snapshot T1 but absent in T2 is presumed
sold during the (T1, T2) window. The price from the most recent snapshot
where it was present is used as the asking-price proxy.
"""

from __future__ import annotations

import logging
import time

import requests_cache

from gibson_price.schema import GuitarListing

log = logging.getLogger(__name__)

WAYBACK_API = "https://web.archive.org/web/timemap/link/"
WAYBACK_FETCH = "https://web.archive.org/web/{ts}/{url}"
RATE_LIMIT_SECONDS = 1.5

DEALERS = [
    "https://guitars.com/inventory/",       # Gruhn
    "https://cartervintage.com/shop/",
    "https://www.elderly.com/products/",
    "https://www.folkwaymusic.com/",
]

_session = requests_cache.CachedSession(
    cache_name=".cache/wayback",
    expire_after=60 * 60 * 24 * 90,
    allowable_methods=("GET",),
)
_session.headers.update({"User-Agent": "gibson-price-research/0.1"})


def list_snapshots(url: str) -> list[str]:
    """Return Wayback timestamps available for a dealer URL."""
    resp = _session.get(f"{WAYBACK_API}{url}", timeout=30)
    if resp.status_code != 200:
        log.warning("Wayback timemap %s for %s", resp.status_code, url)
        return []
    timestamps = []
    for line in resp.text.splitlines():
        if "datetime=" in line:
            try:
                ts = line.split('datetime="')[1].split('"')[0]
                timestamps.append(ts.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")[:14])
            except IndexError:
                continue
    return timestamps


def fetch_snapshot(url: str, ts: str) -> str | None:
    """Fetch a single Wayback snapshot's HTML."""
    time.sleep(RATE_LIMIT_SECONDS)
    resp = _session.get(WAYBACK_FETCH.format(ts=ts, url=url), timeout=60)
    if resp.status_code != 200:
        return None
    return resp.text


def ingest_dealer(url: str, max_snapshots: int = 6) -> list[GuitarListing]:
    """Skeleton: pull recent snapshots, diff to infer sold items.

    Production version would diff snapshot N vs N-1 to detect items removed
    (= probable sale), and emit GuitarListing records for those items at
    the price they were last listed at. The parsing is dealer-specific —
    each dealer needs its own DOM extractor. Returns [] for now; populated
    when the per-dealer parsers are wired up.
    """
    log.info("Stub: would ingest %s, %d snapshots", url, max_snapshots)
    return []
