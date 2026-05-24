"""Generic dealer fetcher: sitemap.xml + JSON-LD.

The big idea: most modern e-commerce sites are crawlable with a *single*
generic function. Add a dealer = one line in the registry. No per-site
HTML selectors, no bespoke parser to maintain.

Pipeline:
  1. Walk site's sitemap to enumerate product URLs (polite, comprehensive)
  2. Fetch each product page
  3. Extract schema.org/Product blocks via JSON-LD (stable across themes)
  4. Apply title parser for (brand, model, year) where the structured data lacks it
  5. Drop low-confidence extractions; emit GuitarListing records

When sitemap+JSON-LD fails, fall back to a category-page HTML scrape with
JSON-LD-on-product-page extraction (still avoids per-site selector maintenance).
"""

from __future__ import annotations

import logging
from datetime import date

from gibson_price.features.condition import normalize_condition
from gibson_price.ingest import common_crawl, jsonld, sitemap
from gibson_price.ingest.base import PolitenessConfig, make_session, polite_get
from gibson_price.ingest.title_parser import parse_title
from gibson_price.schema import GuitarListing

log = logging.getLogger(__name__)

CFG = PolitenessConfig(cache_name="generic_dealer", rate_limit_seconds=2.5)
_session = make_session(CFG)


def fetch_via_sitemap_jsonld(
    base_url: str,
    *,
    dealer_name: str,
    product_path: str = "/products/",
    max_products: int = 500,
    brand_filter: tuple[str, ...] = (),
) -> list[GuitarListing]:
    """Pull every product URL from the sitemap, extract via JSON-LD on each page."""
    entries = sitemap.crawl_sitemap(base_url, path_filter=product_path, max_entries=max_products)
    if not entries:
        log.info("%s: no sitemap entries found at %s for path %s", dealer_name, base_url, product_path)
        return []

    out: list[GuitarListing] = []
    for entry in entries:
        listing = _fetch_one_product(entry.url, dealer_name, entry.lastmod)
        if listing is None:
            continue
        if brand_filter and listing.brand not in brand_filter:
            continue
        out.append(listing)
    return out


def fetch_via_common_crawl(
    *,
    dealer_name: str,
    domain: str,
    product_path: str = "products",
    max_records: int = 1000,
    brand_filter: tuple[str, ...] = (),
) -> list[GuitarListing]:
    """Pull historical product snapshots from Common Crawl — works on dealers
    that have since closed or that block direct scraping. Yields one record
    per (URL, capture-time) so the same product seen across years produces
    multiple records (and a price-history time series).
    """
    pattern = f"{domain}/{product_path}/*"
    records = common_crawl.cdx_search(url_pattern=pattern, max_records_per_index=max_records)
    records = common_crawl.deduplicate(records)
    log.info("%s: %d unique CC records for %s", dealer_name, len(records), pattern)
    out: list[GuitarListing] = []
    for rec in records:
        html = common_crawl.fetch_warc_record(rec)
        if not html:
            continue
        listing = _parse_html_jsonld(html, rec.url, dealer_name, source_id_suffix=rec.timestamp)
        if listing is None:
            continue
        if brand_filter and listing.brand not in brand_filter:
            continue
        # Tag with the snapshot date as the "listing_date" so we get historical signal
        try:
            listing.listing_date = date(
                int(rec.timestamp[:4]),
                int(rec.timestamp[4:6]),
                int(rec.timestamp[6:8]),
            )
            listing.source = "dealer_archive"
            listing.price_confidence = "asking"
        except (ValueError, IndexError):
            pass
        out.append(listing)
    return out


def _fetch_one_product(url: str, dealer_name: str, lastmod: date | None) -> GuitarListing | None:
    resp = polite_get(_session, url, CFG)
    if resp is None or resp.status_code != 200:
        return None
    listing = _parse_html_jsonld(resp.text, url, dealer_name)
    if listing and lastmod:
        listing.listing_date = lastmod
    return listing


def _parse_html_jsonld(
    html: str,
    url: str,
    dealer_name: str,
    *,
    source_id_suffix: str | None = None,
) -> GuitarListing | None:
    products = jsonld.extract_products(html)
    if not products:
        return None
    product = products[0]  # most sites have one Product per product page

    # JSON-LD often has a clean `brand` field; combine with title parsing for model + year.
    parsed = parse_title(product.name)
    brand = parsed.brand
    if not brand and product.brand:
        # Re-run brand resolution against the structured `brand` field
        re_parsed = parse_title(f"{product.brand} {product.name}")
        brand = re_parsed.brand
        if re_parsed.confidence > parsed.confidence:
            parsed = re_parsed

    if brand is None or parsed.model_family is None or parsed.confidence < 0.4:
        return None
    if product.price_usd is None or product.price_usd <= 0:
        return None
    if product.currency and product.currency not in ("USD", None):
        # Skip non-USD for now; conversion would need an FX feed
        return None

    desc = product.description or ""
    cond = normalize_condition(desc) or normalize_condition(product.name)
    source_id = product.sku or product.url or url
    if source_id_suffix:
        source_id = f"{source_id}@{source_id_suffix}"

    return GuitarListing(
        source="dealer_custom",
        source_listing_id=f"{dealer_name}:{source_id}",
        brand=brand,  # type: ignore[arg-type]
        model_family=parsed.model_family,
        year=parsed.year,
        condition_grade=cond,
        price_usd=product.price_usd,
        price_confidence="asking",
        is_sold=product.in_stock is False,  # JSON-LD OutOfStock is a sold signal
        listing_date=product.date_published,
        description=desc[:2000],
        url=product.url or url,
        extraction_confidence=parsed.confidence,
    )
