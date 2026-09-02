"""Rewrite the "Latest:" line in README.md from the blog's Atom feed.

Run by .github/workflows/latest-post.yml on a schedule. Standard library only,
so the runner needs nothing installed. Exits 0 whether or not anything changed;
the workflow decides whether to commit by checking git diff.
"""

from __future__ import annotations

import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

FEED_URL = "https://jeremysnr.github.io/feed.xml"
README = Path(__file__).resolve().parent.parent / "README.md"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
BLOCK = re.compile(
    r"(<!-- LATEST-POST:START -->\n).*?(\n<!-- LATEST-POST:END -->)",
    re.DOTALL,
)


def latest_entry() -> tuple[str, str]:
    """Return (title, url) of the most recently published entry."""
    with urllib.request.urlopen(FEED_URL, timeout=30) as response:
        root = ET.fromstring(response.read())

    entries: list[tuple[str, str, str]] = []
    for entry in root.findall("a:entry", ATOM):
        title = (entry.findtext("a:title", default="", namespaces=ATOM) or "").strip()
        link = next(
            (
                el.get("href")
                for el in entry.findall("a:link", ATOM)
                if el.get("rel", "alternate") == "alternate" and el.get("href")
            ),
            None,
        )
        published = (
            entry.findtext("a:published", default="", namespaces=ATOM)
            or entry.findtext("a:updated", default="", namespaces=ATOM)
            or ""
        )
        if title and link:
            entries.append((published, title, link))

    if not entries:
        sys.exit("feed contained no usable entries; leaving README untouched")

    entries.sort(reverse=True)  # ISO 8601 timestamps sort lexically
    _, title, link = entries[0]
    return title, link


def main() -> None:
    title, link = latest_entry()
    safe_title = title.replace("[", "\\[").replace("]", "\\]")
    line = f"Latest: [{safe_title}]({link})"

    original = README.read_text(encoding="utf-8")
    if not BLOCK.search(original):
        sys.exit("README.md has no LATEST-POST markers; nothing to update")

    updated = BLOCK.sub(lambda m: f"{m.group(1)}{line}{m.group(2)}", original, count=1)
    if updated == original:
        print(f"unchanged: {line}")
        return

    README.write_text(updated, encoding="utf-8", newline="\n")
    print(f"updated: {line}")


if __name__ == "__main__":
    main()
