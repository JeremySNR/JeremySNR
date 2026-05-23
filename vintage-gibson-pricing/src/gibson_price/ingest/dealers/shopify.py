"""Generic Shopify storefront product fetcher.

Shopify exposes `/products.json?limit=250&page=N` on every public storefront.
The endpoint returns the same data the anonymous browser sees, in machine-
readable form. No auth needed. Returns active inventory only — for sold
history we cross-reference Wayback snapshots in `dealer_archive.py`.

This single function works for *every* Shopify-based dealer in the registry.
Carter Vintage, Norman's, Emerald City, Imperial, Wildwood — all hit by the
same code path.

ToS note: this endpoint is publicly documented by Shopify and serves data
already exposed to anonymous browsers. Unlike scraping a paid product
(e.g. Reverb Price Guide), pulling Shopify storefront products is a
standard interoperability pattern.
"""

from __future__ import annotations

import logging
from datetime import date

from gibson_price.features.condition import normalize_condition
from gibson_price.ingest.base import PolitenessConfig, make_session, polite_get
from gibson_price.ingest.title_parser import parse_title
from gibson_price.schema import Brand, GuitarListing

log = logging.getLogger(__name__)

CFG = PolitenessConfig(
    cache_name="shopify",
    expire_after_seconds=60 * 60 * 12,
    rate_limit_seconds=2.0,
)
_session = make_session(CFG)


def fetch_products(
    base_url: str,
    *,
    dealer_name: str,
    brand_filter: tuple[str, ...] = (),
    max_pages: int = 20,
    per_page: int = 250,
) -> list[GuitarListing]:
    """Iterate /products.json across pages and return parsed GuitarListings.

    `brand_filter` keeps only items whose extracted brand is in the tuple.
    Empty tuple keeps everything.
    """
    results: list[GuitarListing] = []
    base = base_url.rstrip("/")
    for page in range(1, max_pages + 1):
        url = f"{base}/products.json"
        resp = polite_get(_session, url, CFG, params={"limit": per_page, "page": page})
        if resp is None:
            break
        if resp.status_code in (401, 403, 404):
            log.info("%s returned %d for /products.json — endpoint disabled or gated", dealer_name, resp.status_code)
            break
        if resp.status_code != 200:
            log.warning("%s products.json %d on page %d", dealer_name, resp.status_code, page)
            break
        try:
            payload = resp.json()
        except ValueError:
            log.warning("%s products.json page %d returned non-JSON", dealer_name, page)
            break
        products = payload.get("products", [])
        if not products:
            break
        for raw in products:
            listing = _to_listing(raw, base, dealer_name)
            if listing is None:
                continue
            if brand_filter and listing.brand not in brand_filter:
                continue
            results.append(listing)
        if len(products) < per_page:
            break
    return results


def _to_listing(raw: dict, base: str, dealer_name: str) -> GuitarListing | None:
    title = raw.get("title") or ""
    parsed = parse_title(title)
    if parsed.confidence < 0.4 or parsed.brand is None or parsed.model_family is None:
        return None

    variants = raw.get("variants") or []
    if not variants:
        return None
    # Shopify variant prices come as strings in dollars (or sometimes cents);
    # the convention on storefront /products.json is dollar-decimal strings.
    try:
        price_usd = float(variants[0].get("price"))
    except (TypeError, ValueError):
        return None
    if price_usd <= 0:
        return None

    body_html = raw.get("body_html") or ""
    description = _strip_html(body_html)
    cond = normalize_condition(description) or normalize_condition(title)

    handle = raw.get("handle") or ""
    url = f"{base}/products/{handle}" if handle else base

    return GuitarListing(
        source="dealer_shopify",
        source_listing_id=f"{dealer_name}:{raw.get('id', handle)}",
        brand=parsed.brand,  # type: ignore[arg-type]
        model_family=parsed.model_family,
        year=parsed.year,
        condition_grade=cond,
        price_usd=price_usd,
        price_confidence="asking",
        is_sold=False,
        listing_date=_parse_iso_date(raw.get("created_at")),
        description=description[:2000],
        url=url,
        extraction_confidence=parsed.confidence,
    )


def _strip_html(html: str) -> str:
    """Very light HTML strip — descriptions are short, regex is fine."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def supported_brands_to_filter(brand_focus: tuple[str, ...]) -> tuple[Brand, ...]:
    """Coerce string brands from DealerConfig to the Brand literal type used in filtering."""
    valid: set[Brand] = {"Gibson", "Martin", "Guild", "Gretsch", "Epiphone", "Other"}
    return tuple(b for b in brand_focus if b in valid)  # type: ignore[misc]
