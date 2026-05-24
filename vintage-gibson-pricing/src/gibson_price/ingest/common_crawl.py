"""Common Crawl URL Index client — historical archive of the web, free.

Common Crawl publishes ~3 PB of crawled web data per index (one or two new
indexes per month, 10+ years of history). Their CDX URL Index lets you query
for every captured URL matching a domain pattern — and for each match, gives
you a WARC file + byte offset + length so you can fetch *just that page's
bytes* directly from S3 without re-crawling the source site.

For "find every guitar that's ever sold online", this is the single most
powerful unlock:

  - Free, no auth, no API limits
  - Polite by design (you're hitting S3, not the dealer site)
  - Covers years of historical snapshots per domain
  - Returns the exact HTML the crawler saw, so JSON-LD extraction works

Workflow per dealer:
  1. cdx_search(domain="emeraldcityguitars.com", path_pattern="*/products/*")
     -> list of CDX records over all indexes
  2. fetch_warc_record(record) -> the HTML of that snapshot
  3. jsonld.extract_products(html) -> structured Product records
  4. Combine snapshots over time -> historical sold inference

See https://commoncrawl.org/get-started for the spec.
"""

from __future__ import annotations

import gzip
import json
import logging
from dataclasses import dataclass
from io import BytesIO

from gibson_price.ingest.base import PolitenessConfig, make_session, polite_get

log = logging.getLogger(__name__)

CC_INDEX_LIST = "https://index.commoncrawl.org/collinfo.json"
WARC_BASE = "https://data.commoncrawl.org/"

CFG = PolitenessConfig(
    cache_name="common_crawl",
    expire_after_seconds=60 * 60 * 24 * 90,
    rate_limit_seconds=0.5,  # CC's S3 + index servers don't need much politeness
)
_session = make_session(CFG)


@dataclass
class CdxRecord:
    url: str
    timestamp: str          # 14-digit YYYYMMDDhhmmss
    status: int
    digest: str
    warc_filename: str
    warc_offset: int
    warc_length: int
    index_name: str         # e.g. "CC-MAIN-2024-30"


def list_indexes(limit: int | None = None) -> list[str]:
    """Return Common Crawl index identifiers, newest first."""
    resp = polite_get(_session, CC_INDEX_LIST, CFG)
    if resp is None or resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return []
    ids = [entry["id"] for entry in data if "id" in entry]
    return ids[:limit] if limit else ids


def cdx_search(
    *,
    url_pattern: str,
    indexes: list[str] | None = None,
    max_records_per_index: int = 500,
) -> list[CdxRecord]:
    """Search the CDX index for records matching `url_pattern` (CDX glob syntax).

    Examples of url_pattern:
        "emeraldcityguitars.com/products/*"
        "*.cartervintage.com/*"
        "guitars.com/inventory/*"
    """
    indexes = indexes or list_indexes(limit=8)  # last ~year by default
    results: list[CdxRecord] = []
    for index_name in indexes:
        url = f"https://index.commoncrawl.org/{index_name}-index"
        params = {
            "url": url_pattern,
            "output": "json",
            "limit": max_records_per_index,
        }
        resp = polite_get(_session, url, CFG, params=params)
        if resp is None or resp.status_code != 200:
            log.debug("CDX index %s returned %s", index_name, resp.status_code if resp else "no response")
            continue
        for line in resp.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                results.append(CdxRecord(
                    url=row["url"],
                    timestamp=row["timestamp"],
                    status=int(row.get("status", 0)),
                    digest=row.get("digest", ""),
                    warc_filename=row["filename"],
                    warc_offset=int(row["offset"]),
                    warc_length=int(row["length"]),
                    index_name=index_name,
                ))
            except (KeyError, ValueError):
                continue
    return results


def fetch_warc_record(record: CdxRecord) -> str | None:
    """Fetch just the bytes for this WARC record from S3 (HTTP Range request)."""
    url = WARC_BASE + record.warc_filename
    headers = {"Range": f"bytes={record.warc_offset}-{record.warc_offset + record.warc_length - 1}"}
    resp = polite_get(_session, url, CFG, headers=headers)
    if resp is None or resp.status_code not in (200, 206):
        return None
    try:
        decompressed = gzip.GzipFile(fileobj=BytesIO(resp.content)).read()
    except OSError as e:
        log.debug("WARC gunzip failed: %s", e)
        return None
    text = decompressed.decode("utf-8", errors="replace")
    # WARC record = HTTP-style header, blank line, then payload
    parts = text.split("\r\n\r\n", 2)
    if len(parts) < 3:
        return None
    # parts[0] is the WARC header, parts[1] is the HTTP response header, parts[2] is the body
    return parts[2]


def deduplicate(records: list[CdxRecord]) -> list[CdxRecord]:
    """Dedupe by digest — same content seen across multiple indexes."""
    seen: dict[str, CdxRecord] = {}
    for r in records:
        existing = seen.get(r.digest)
        if existing is None or r.timestamp > existing.timestamp:
            seen[r.digest] = r
    return sorted(seen.values(), key=lambda r: r.timestamp)
