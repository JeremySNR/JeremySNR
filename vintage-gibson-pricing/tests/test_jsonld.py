"""Tests for the JSON-LD product extractor — the workhorse of the generic ingest."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gibson_price.ingest.jsonld import extract_products

SHOPIFY_LIKE_HTML = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "1956 Gibson J-45 Sunburst",
  "brand": {"@type": "Brand", "name": "Gibson"},
  "description": "All original 1956 J-45 in excellent condition. Original case.",
  "sku": "GIBSON-J45-1956-001",
  "url": "https://example-dealer.com/products/gibson-j45-1956",
  "image": ["https://example-dealer.com/images/j45.jpg"],
  "offers": {
    "@type": "Offer",
    "price": "8995.00",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock"
  }
}
</script>
</head><body>...</body></html>
"""

GRAPH_WRAPPED_HTML = """
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {"@type": "WebSite", "name": "Some Dealer"},
    {
      "@type": "Product",
      "name": "1942 Martin D-28",
      "brand": "Martin",
      "offers": {"@type": "Offer", "price": 95000, "priceCurrency": "USD", "availability": "https://schema.org/OutOfStock"}
    }
  ]
}
</script>
"""

MULTI_BLOCK_HTML = """
<script type="application/ld+json">{"@type": "BreadcrumbList", "name": "navigation"}</script>
<script type="application/ld+json">
{"@type": "Product", "name": "1965 Gibson Hummingbird",
 "brand": "Gibson",
 "offers": {"@type": "AggregateOffer", "lowPrice": 7500, "highPrice": 9500, "priceCurrency": "USD"}}
</script>
"""

MALFORMED_HTML = """
<script type="application/ld+json">{invalid json,}</script>
<script type="application/ld+json">{"@type": "Product", "name": "1953 Gibson LG-2",
 "brand": "Gibson",
 "offers": {"@type": "Offer", "price": "3200.00", "priceCurrency": "USD"}}</script>
"""


def test_basic_shopify_style_product() -> None:
    products = extract_products(SHOPIFY_LIKE_HTML)
    assert len(products) == 1
    p = products[0]
    assert p.name == "1956 Gibson J-45 Sunburst"
    assert p.brand == "Gibson"
    assert p.price_usd == 8995.0
    assert p.currency == "USD"
    assert p.in_stock is True
    assert p.sku == "GIBSON-J45-1956-001"


def test_graph_wrapped_product_extracted() -> None:
    products = extract_products(GRAPH_WRAPPED_HTML)
    assert len(products) == 1
    p = products[0]
    assert p.brand == "Martin"
    assert p.price_usd == 95000.0
    assert p.in_stock is False  # OutOfStock signal


def test_aggregate_offer_lowprice_used() -> None:
    products = extract_products(MULTI_BLOCK_HTML)
    assert len(products) == 1
    p = products[0]
    assert p.price_usd == 7500.0


def test_malformed_block_skipped_others_kept() -> None:
    """A broken JSON-LD block should not prevent extraction of valid neighbours."""
    products = extract_products(MALFORMED_HTML)
    assert len(products) == 1
    assert products[0].name.startswith("1953 Gibson")


def test_empty_html_returns_empty() -> None:
    assert extract_products("") == []
    assert extract_products("<html><body>nothing</body></html>") == []


def test_brand_as_dict() -> None:
    html = """
    <script type="application/ld+json">
    {"@type": "Product", "name": "1939 Martin D-18",
     "brand": {"@type": "Organization", "name": "Martin"},
     "offers": {"@type": "Offer", "price": 18000, "priceCurrency": "USD"}}
    </script>
    """
    products = extract_products(html)
    assert products[0].brand == "Martin"
