"""Wayback Machine CDX API client + snapshot diff utilities.

Used by dealer_archive.py to infer sold items: an item present in snapshot T1
and absent in T2 (and the next M snapshots) is presumed sold at its
last-listed price.

CDX API docs: https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server
The CDX server returns JSON arrays of [urlkey, timestamp, original_url, mimetype, status, digest, length].
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from gibson_price.ingest.base import PolitenessConfig, make_session, polite_get

log = logging.getLogger(__name__)

CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK_FETCH = "https://web.archive.org/web/{ts}/{url}"

CFG = PolitenessConfig(
    cache_name="wayback",
    expire_after_seconds=60 * 60 * 24 * 90,
    rate_limit_seconds=1.5,
)
_session = make_session(CFG)


@dataclass
class Snapshot:
    timestamp: str  # 14-digit YYYYMMDDhhmmss
    url: str
    status: int
    digest: str

    @property
    def datetime(self) -> datetime:
        return datetime.strptime(self.timestamp, "%Y%m%d%H%M%S")

    def fetch_url(self) -> str:
        return WAYBACK_FETCH.format(ts=self.timestamp, url=self.url)


def list_snapshots(
    url: str,
    *,
    from_year: int = 2018,
    to_year: int = 2026,
    limit: int = 200,
    only_200: bool = True,
) -> list[Snapshot]:
    """Return Wayback snapshots for a URL, oldest first."""
    params = {
        "url": url,
        "output": "json",
        "from": f"{from_year}0101",
        "to": f"{to_year}1231",
        "limit": str(limit),
        "collapse": "digest",  # collapse runs of identical content
    }
    if only_200:
        params["filter"] = "statuscode:200"
    resp = polite_get(_session, CDX_API, CFG, params=params)
    if resp is None or resp.status_code != 200:
        log.warning("Wayback CDX failed for %s", url)
        return []
    try:
        rows = resp.json()
    except json.JSONDecodeError:
        return []
    # First row is the header
    snapshots = []
    for row in rows[1:]:
        if len(row) < 7:
            continue
        _, ts, orig_url, _, status, digest, _ = row[:7]
        try:
            snapshots.append(Snapshot(ts, orig_url, int(status), digest))
        except ValueError:
            continue
    snapshots.sort(key=lambda s: s.timestamp)
    return snapshots


def fetch_snapshot_html(snapshot: Snapshot) -> str | None:
    """Fetch a single archived page's HTML."""
    resp = polite_get(_session, snapshot.fetch_url(), CFG)
    if resp is None or resp.status_code != 200:
        return None
    return resp.text


@dataclass
class SnapshotDiff:
    """Items present in earlier snapshot but absent in later -> presumed sold."""

    presumed_sold: list[str]  # stable product ids
    still_listed: list[str]
    new_listed: list[str]


def diff_snapshots(
    earlier_ids: list[str], later_ids: list[str], *, min_disappearances: int = 1
) -> SnapshotDiff:
    """Naive diff. The `min_disappearances` arg is consumed by the caller when
    chaining multiple snapshots — see dealer_archive.infer_sold_from_history.
    """
    earlier_set = set(earlier_ids)
    later_set = set(later_ids)
    return SnapshotDiff(
        presumed_sold=sorted(earlier_set - later_set),
        still_listed=sorted(earlier_set & later_set),
        new_listed=sorted(later_set - earlier_set),
    )


def infer_sold_from_history(
    id_history: list[tuple[str, set[str]]],
    *,
    min_consecutive_absences: int = 2,
) -> set[str]:
    """Given a chronological list of (snapshot_ts, set_of_product_ids), return the
    set of IDs that disappeared and stayed gone for at least min_consecutive_absences
    snapshots — filtering out transient outages or re-slugging.
    """
    if len(id_history) < min_consecutive_absences + 1:
        return set()
    all_ever_seen: set[str] = set()
    for _, ids in id_history:
        all_ever_seen |= ids
    presumed_sold: set[str] = set()
    for pid in all_ever_seen:
        # Find the last snapshot where pid was present
        last_seen_idx = max(
            (i for i, (_, ids) in enumerate(id_history) if pid in ids),
            default=-1,
        )
        if last_seen_idx < 0:
            continue
        # How many subsequent snapshots are missing pid?
        subsequent = len(id_history) - 1 - last_seen_idx
        if subsequent >= min_consecutive_absences:
            presumed_sold.add(pid)
    return presumed_sold
