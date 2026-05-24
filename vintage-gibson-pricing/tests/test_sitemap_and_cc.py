"""Tests for sitemap.xml parsing and Common Crawl CDX record handling.

We can't validate live HTTP from a sandbox, but we can validate the parsers
against fixture XML / JSON that mirrors the live formats.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gibson_price.ingest.common_crawl import CdxRecord, deduplicate
from gibson_price.ingest.sitemap import _parse_sitemap_xml

SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example-dealer.com/sitemap_products_1.xml</loc><lastmod>2026-05-01</lastmod></sitemap>
  <sitemap><loc>https://example-dealer.com/sitemap_products_2.xml</loc></sitemap>
</sitemapindex>
"""

SITEMAP_LEAF_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example-dealer.com/products/gibson-j45-1956</loc><lastmod>2026-04-22</lastmod></url>
  <url><loc>https://example-dealer.com/products/martin-d28-1939</loc><lastmod>2026-04-15</lastmod></url>
  <url><loc>https://example-dealer.com/about</loc></url>
</urlset>
"""


def test_sitemap_index_returns_nested_urls() -> None:
    nested, entries = _parse_sitemap_xml(SITEMAP_INDEX_XML)
    assert len(nested) == 2
    assert "sitemap_products_1.xml" in nested[0]
    assert entries == []


def test_sitemap_leaf_returns_url_entries() -> None:
    nested, entries = _parse_sitemap_xml(SITEMAP_LEAF_XML)
    assert nested == []
    assert len(entries) == 3
    j45 = next(e for e in entries if "j45" in e.url)
    assert j45.lastmod.year == 2026
    no_lastmod = next(e for e in entries if e.url.endswith("/about"))
    assert no_lastmod.lastmod is None


def test_cdx_dedup_keeps_latest_per_digest() -> None:
    records = [
        CdxRecord(url="u1", timestamp="20230101000000", status=200, digest="A",
                  warc_filename="x.warc.gz", warc_offset=0, warc_length=10, index_name="i1"),
        CdxRecord(url="u1", timestamp="20240101000000", status=200, digest="A",
                  warc_filename="x.warc.gz", warc_offset=0, warc_length=10, index_name="i2"),
        CdxRecord(url="u2", timestamp="20230601000000", status=200, digest="B",
                  warc_filename="y.warc.gz", warc_offset=0, warc_length=10, index_name="i1"),
    ]
    deduped = deduplicate(records)
    assert len(deduped) == 2
    digests = {r.digest: r.timestamp for r in deduped}
    assert digests["A"] == "20240101000000"  # newest kept
    assert digests["B"] == "20230601000000"
