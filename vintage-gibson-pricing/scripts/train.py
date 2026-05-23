"""CLI entry: train a model and write artifacts/model.pkl + reports/eval.html."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gibson_price.models.train import main  # noqa: E402

if __name__ == "__main__":
    main()
