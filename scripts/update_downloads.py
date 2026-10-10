"""Write download-count badges for the README.

Sums GitHub release asset downloads across public, non-fork repos and npm
downloads across every package JeremySNR maintains, then writes shields.io
endpoint JSON into stats/. Run by .github/workflows/latest-post.yml on a
schedule. Standard library only. Set GITHUB_TOKEN to avoid API rate limits.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

USER = "JeremySNR"
NPM_MAINTAINER = "jeremysnr"
NPM_EPOCH = date(2025, 1, 1)  # before the first package was published
STATS = Path(__file__).resolve().parent.parent / "stats"
COLOR = "FFE81F"
LABEL_COLOR = "000000"


def get_json(url: str) -> object:
    headers = {"User-Agent": f"{USER}-profile-stats"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def github_release_downloads() -> int:
    total = 0
    page = 1
    while True:
        repos = get_json(
            f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}"
        )
        if not repos:
            return total
        for repo in repos:
            if repo["fork"] or repo["private"]:
                continue
            releases = get_json(
                f"https://api.github.com/repos/{USER}/{repo['name']}/releases?per_page=100"
            )
            total += sum(a["download_count"] for r in releases for a in r["assets"])
        page += 1


def npm_downloads() -> int:
    search = get_json(
        f"https://registry.npmjs.org/-/v1/search?text=maintainer:{NPM_MAINTAINER}&size=250"
    )
    packages = [obj["package"]["name"] for obj in search["objects"]]
    total = 0
    today = date.today()
    for name in packages:
        # The point API caps each query at 18 months, so walk in one-year windows.
        start = NPM_EPOCH
        while start <= today:
            end = min(start + timedelta(days=364), today)
            point = get_json(f"https://api.npmjs.org/downloads/point/{start}:{end}/{name}")
            total += point.get("downloads", 0)
            start = end + timedelta(days=1)
    return total


def humanise(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def write_badge(name: str, label: str, count: int) -> None:
    badge = {
        "schemaVersion": 1,
        "label": label,
        "message": humanise(count),
        "color": COLOR,
        "labelColor": LABEL_COLOR,
    }
    (STATS / f"{name}.json").write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    try:
        releases = github_release_downloads()
        npm = npm_downloads()
    except Exception as exc:  # leave the last good numbers in place
        sys.exit(f"could not fetch download counts: {exc}")

    STATS.mkdir(exist_ok=True)
    write_badge("downloads-total", "total downloads", releases + npm)
    write_badge("downloads-releases", "app downloads", releases)
    write_badge("downloads-npm", "npm installs", npm)
    print(f"releases={releases} npm={npm} total={releases + npm}")


if __name__ == "__main__":
    main()
