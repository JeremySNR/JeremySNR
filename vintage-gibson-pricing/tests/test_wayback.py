"""Tests for the Wayback Machine diff logic — sold-state inference."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gibson_price.ingest.wayback import diff_snapshots, infer_sold_from_history


def test_diff_basic_appearance_and_removal() -> None:
    diff = diff_snapshots(["a", "b", "c"], ["b", "c", "d"])
    assert diff.presumed_sold == ["a"]
    assert diff.still_listed == ["b", "c"]
    assert diff.new_listed == ["d"]


def test_infer_sold_requires_consecutive_absences() -> None:
    """An item absent in just one snapshot shouldn't be flagged as sold —
    could be a transient outage or a temporary slug change."""
    history = [
        ("20240101000000", {"a", "b"}),
        ("20240201000000", {"a"}),       # b missing once
        ("20240301000000", {"a", "b"}),  # b returns
    ]
    presumed = infer_sold_from_history(history, min_consecutive_absences=2)
    assert "b" not in presumed


def test_infer_sold_with_two_consecutive_absences() -> None:
    history = [
        ("20240101000000", {"a", "b"}),
        ("20240201000000", {"a", "b"}),
        ("20240301000000", {"a"}),       # b gone
        ("20240401000000", {"a"}),       # b still gone
    ]
    presumed = infer_sold_from_history(history, min_consecutive_absences=2)
    assert presumed == {"b"}


def test_infer_sold_ignores_items_only_in_latest_snapshot() -> None:
    """A new arrival shouldn't be flagged."""
    history = [
        ("20240101000000", {"a"}),
        ("20240201000000", {"a"}),
        ("20240301000000", {"a", "c"}),
    ]
    presumed = infer_sold_from_history(history, min_consecutive_absences=2)
    assert presumed == set()


def test_too_few_snapshots_returns_empty() -> None:
    history = [("20240101000000", {"a", "b"})]
    presumed = infer_sold_from_history(history, min_consecutive_absences=2)
    assert presumed == set()
