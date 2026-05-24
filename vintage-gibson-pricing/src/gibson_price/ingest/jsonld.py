"""JSON-LD product extractor — the single most-robust scraping primitive.

Most modern e-commerce sites (Shopify, WooCommerce, BigCommerce, Magento,
Squarespace, custom) embed product data in `<script type="application/ld+json">`
blocks following the schema.org/Product vocabulary. These blocks are:

  - Standardized across platforms
  - Stable across theme changes (search engines depend on them)
  - Often more complete than visible HTML
  - Include price, availability, brand, model, description, image URLs

This module extracts schema.org/Product entries from any HTML page,
normalizing the heterogeneity in how sites wrap them (single object,
array, @graph, nested ItemList).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_JSONLD_TAG = re.compile(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)


@dataclass
class JsonLdProduct:
    name: str
    brand: str | None
    description: str | None
    price_usd: float | None
    currency: str | None
    sku: str | None
    url: str | None
    image: str | None
    in_stock: bool | None
    date_published: date | None


def _walk_for_products(node) -> list[dict]:
    """Walk a parsed JSON-LD structure and yield every Product-typed dict."""
    out: list[dict] = []
    if isinstance(node, dict):
        types = node.get("@type")
        type_list = [types] if isinstance(types, str) else (types or [])
        if "Product" in type_list:
            out.append(node)
        # Recurse into @graph (most common wrapper) and itemListElement
        for key in ("@graph", "itemListElement", "hasPart", "mainEntity"):
            if key in node:
                out.extend(_walk_for_products(node[key]))
    elif isinstance(node, list):
        for item in node:
            out.extend(_walk_for_products(item))
    return out


def _extract_price(offers) -> tuple[float | None, str | None, bool | None]:
    """Offers can be a single Offer, an AggregateOffer, or a list."""
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    if not isinstance(offers, dict):
        return None, None, None
    price_val = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice")
    if price_val is None:
        price_spec = offers.get("priceSpecification") or {}
        if isinstance(price_spec, dict):
            price_val = price_spec.get("price")
    try:
        price = float(str(price_val).replace(",", "").replace("$", "")) if price_val is not None else None
    except (ValueError, TypeError):
        price = None
    currency = offers.get("priceCurrency") or offers.get("currency")
    availability = offers.get("availability") or ""
    in_stock = None
    if isinstance(availability, str):
        if "InStock" in availability:
            in_stock = True
        elif "OutOfStock" in availability or "SoldOut" in availability:
            in_stock = False
    return price, currency, in_stock


def _extract_brand(brand_node) -> str | None:
    if isinstance(brand_node, str):
        return brand_node
    if isinstance(brand_node, dict):
        return brand_node.get("name")
    if isinstance(brand_node, list) and brand_node:
        return _extract_brand(brand_node[0])
    return None


def _extract_image(image_node) -> str | None:
    if isinstance(image_node, str):
        return image_node
    if isinstance(image_node, list) and image_node:
        return _extract_image(image_node[0])
    if isinstance(image_node, dict):
        return image_node.get("url") or image_node.get("contentUrl")
    return None


def _normalize_product(raw: dict) -> JsonLdProduct | None:
    name = raw.get("name") or raw.get("title")
    if not name:
        return None
    price, currency, in_stock = _extract_price(raw.get("offers"))
    desc = raw.get("description")
    if isinstance(desc, dict):
        desc = desc.get("@value")

    date_pub = raw.get("datePublished") or raw.get("dateCreated") or raw.get("releaseDate")
    parsed_date: date | None = None
    if isinstance(date_pub, str):
        try:
            parsed_date = date.fromisoformat(date_pub[:10])
        except ValueError:
            parsed_date = None

    return JsonLdProduct(
        name=str(name).strip(),
        brand=_extract_brand(raw.get("brand")),
        description=str(desc).strip() if desc else None,
        price_usd=price,
        currency=currency,
        sku=raw.get("sku") or raw.get("mpn") or raw.get("productID"),
        url=raw.get("url"),
        image=_extract_image(raw.get("image")),
        in_stock=in_stock,
        date_published=parsed_date,
    )


def extract_products(html: str) -> list[JsonLdProduct]:
    """Return every schema.org/Product found in any JSON-LD block on the page."""
    if not html:
        return []
    products: list[JsonLdProduct] = []
    # Regex pre-scan is fast and avoids parsing the whole document with BS4 when there are no LD blocks.
    blocks = _JSONLD_TAG.findall(html)
    if not blocks:
        # Fall back to BS4 in case the script tag has unusual attribute ordering.
        soup = BeautifulSoup(html, "html.parser")
        blocks = [s.string or s.get_text() for s in soup.find_all("script", type="application/ld+json")]
        blocks = [b for b in blocks if b]

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            # Some sites emit invalid JSON-LD with trailing commas or HTML entities. Best-effort skip.
            log.debug("Skipping malformed JSON-LD block")
            continue
        for raw_product in _walk_for_products(parsed):
            normalized = _normalize_product(raw_product)
            if normalized:
                products.append(normalized)
    return products
