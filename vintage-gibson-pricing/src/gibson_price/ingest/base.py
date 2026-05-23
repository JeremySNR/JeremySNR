"""Shared infrastructure for all ingest sources.

Provides a cached, rate-limited, robots.txt-respecting HTTP session and a
PolitenessConfig dataclass that every source uses. Centralising this means
adding a new dealer is a one-file change and the politeness baseline is
applied uniformly.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests_cache

log = logging.getLogger(__name__)

USER_AGENT = (
    "gibson-price-research/0.1 "
    "(+https://github.com/JeremySNR/JeremySNR; personal research)"
)
CACHE_ROOT = Path(".cache")


@dataclass(frozen=True)
class PolitenessConfig:
    """One config per source. Tight defaults; raise rate_limit_seconds for picky hosts."""

    cache_name: str
    expire_after_seconds: int = 60 * 60 * 24 * 7
    rate_limit_seconds: float = 2.5
    timeout_seconds: int = 30
    respect_robots: bool = True


_last_hit_per_host: dict[str, float] = {}
_last_hit_lock = Lock()


def _wait_for_host(host: str, rate_limit_seconds: float) -> None:
    """Per-host rate-limit. Threadsafe."""
    with _last_hit_lock:
        last = _last_hit_per_host.get(host, 0.0)
        wait = rate_limit_seconds - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _last_hit_per_host[host] = time.time()


def make_session(cfg: PolitenessConfig) -> requests_cache.CachedSession:
    cache_path = CACHE_ROOT / cfg.cache_name
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    session = requests_cache.CachedSession(
        cache_name=str(cache_path),
        expire_after=cfg.expire_after_seconds,
        allowable_methods=("GET",),
    )
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.8"})
    return session


_robots_cache: dict[str, RobotFileParser | None] = {}


def can_fetch(url: str) -> bool:
    """Check robots.txt for the URL's host. Cached per-host."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base not in _robots_cache:
        rp = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
            _robots_cache[base] = rp
        except Exception as e:
            log.warning("robots.txt fetch failed for %s: %s — assuming allow", base, e)
            _robots_cache[base] = None
    rp = _robots_cache[base]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def polite_get(session, url: str, cfg: PolitenessConfig, **kwargs):
    """robots-check + per-host rate-limit + GET. Returns response or None."""
    if cfg.respect_robots and not can_fetch(url):
        log.warning("robots.txt disallows %s — skipping", url)
        return None
    host = urlparse(url).netloc
    _wait_for_host(host, cfg.rate_limit_seconds)
    try:
        return session.get(url, timeout=cfg.timeout_seconds, **kwargs)
    except Exception as e:
        log.warning("GET %s failed: %s", url, e)
        return None
