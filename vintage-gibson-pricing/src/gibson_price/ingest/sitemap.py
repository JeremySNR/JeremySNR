"""sitemap.xml + sitemap_index.xml crawler.

Most production e-commerce sites publish a sitemap (it's required for SEO).
Using it instead of paginating HTML category pages is:

  - Polite (it's what the site operator wants crawlers to use)
  - Comprehensive (lists every product URL the site wants indexed)
  - Stable (doesn't break when pagination or filters change)

We start at `/sitemap.xml`, follow nested `<sitemap>` indexes, and return
flat lists of (url, lastmod_date). Callers filter URLs to those matching
a product-path pattern, then pull each one and run JSON-LD extraction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from gibson_price.ingest.base import PolitenessConfig, make_session, polite_get

log = logging.getLogger(__name__)

CFG = PolitenessConfig(
    cache_name="sitemap",
    expire_after_seconds=60 * 60 * 24,
    rate_limit_seconds=1.5,
)
_session = make_session(CFG)


@dataclass
class SitemapEntry:
    url: str
    lastmod: date | None


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _parse_sitemap_xml(xml: str) -> tuple[list[str], list[SitemapEntry]]:
    """Return (nested_sitemap_urls, url_entries) — sitemap-index files have the former,
    leaf sitemaps have the latter."""
    soup = BeautifulSoup(xml, "xml")
    # Nested sitemap index
    nested = [s.get_text(strip=True) for s in soup.select("sitemap > loc")]
    # Leaf URL entries
    entries = []
    for url_tag in soup.select("url"):
        loc = url_tag.select_one("loc")
        if not loc:
            continue
        lastmod = url_tag.select_one("lastmod")
        entries.append(SitemapEntry(
            url=loc.get_text(strip=True),
            lastmod=_parse_date(lastmod.get_text(strip=True) if lastmod else None),
        ))
    return nested, entries


def crawl_sitemap(
    base_url: str,
    *,
    path_filter: str | None = None,
    max_entries: int = 5000,
    max_nested_depth: int = 3,
) -> list[SitemapEntry]:
    """Walk a site's sitemap tree, returning entries whose URL contains `path_filter`.

    Try `/sitemap.xml` first; many Shopify stores publish `/sitemap_products_1.xml`
    or similar, which we'll discover via the index file.
    """
    base = base_url.rstrip("/")
    seen_sitemaps: set[str] = set()
    pending: list[tuple[str, int]] = [(f"{base}/sitemap.xml", 0)]
    entries: list[SitemapEntry] = []

    while pending and len(entries) < max_entries:
        sitemap_url, depth = pending.pop(0)
        if sitemap_url in seen_sitemaps or depth > max_nested_depth:
            continue
        seen_sitemaps.add(sitemap_url)
        resp = polite_get(_session, sitemap_url, CFG)
        if resp is None or resp.status_code != 200:
            continue
        nested, leaves = _parse_sitemap_xml(resp.text)
        for n in nested:
            pending.append((n, depth + 1))
        for entry in leaves:
            if path_filter and path_filter not in entry.url:
                continue
            # Same-host check — defend against redirects to off-site URLs
            if urlparse(entry.url).netloc and urlparse(entry.url).netloc != urlparse(base).netloc:
                continue
            entries.append(entry)
            if len(entries) >= max_entries:
                break
    return entries
