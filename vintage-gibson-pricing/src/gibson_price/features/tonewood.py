"""Tonewood normalization + era-based defaults.

Vintage Gibson tonewood specs are largely determined by year and model:
  - Tops shift from Adirondack red spruce -> Sitka spruce around 1944-1946.
  - Rosewood backs/sides shift from Brazilian -> Indian rosewood ~1969 (CITES era).
  - Mahogany was used for J-45/Southern Jumbo/LG-1 throughout.
  - Maple was used for J-200/SJ-200 from 1947 onward.
"""

from __future__ import annotations

TOP_WOOD_CANON = {
    "adirondack": "Adirondack",
    "adirondack red spruce": "Adirondack",
    "red spruce": "Adirondack",
    "sitka": "Sitka",
    "sitka spruce": "Sitka",
    "spruce": "Sitka",  # generic — assume Sitka post-1946
    "mahogany": "Mahogany",
}

BACK_SIDES_CANON = {
    "brazilian rosewood": "Brazilian Rosewood",
    "brazilian": "Brazilian Rosewood",
    "indian rosewood": "Indian Rosewood",
    "indian": "Indian Rosewood",
    "rosewood": "Indian Rosewood",  # generic — assume Indian post-1969
    "mahogany": "Mahogany",
    "maple": "Maple",
    "flamed maple": "Maple",
    "birch": "Birch",
}


def canon_top(text: str | None, year: int | None = None) -> str:
    if text:
        norm = text.strip().lower()
        for key, val in TOP_WOOD_CANON.items():
            if key in norm:
                if val == "Sitka" and year and year < 1946:
                    return "Adirondack"
                return val
    # Fallback by year
    if year:
        return "Adirondack" if year < 1946 else "Sitka"
    return "Sitka"


def canon_back_sides(text: str | None, model_family: str | None = None, year: int | None = None) -> str:
    if text:
        norm = text.strip().lower()
        for key, val in BACK_SIDES_CANON.items():
            if key in norm:
                if val == "Indian Rosewood" and year and year < 1969 and "indian" not in norm:
                    return "Brazilian Rosewood"
                return val
    # Fallback from model family
    if model_family:
        mf = model_family.upper()
        if mf in {"J-200", "SJ-200", "DOVE"}:
            return "Maple"
        if mf in {"D-28", "D-35", "D-41", "D-45"}:
            return "Brazilian Rosewood" if year and year < 1969 else "Indian Rosewood"
        if mf in {"J-45", "J-50", "SOUTHERN JUMBO", "HUMMINGBIRD", "L-00", "LG-1", "LG-2", "B-25", "D-18", "000-18"}:
            return "Mahogany"
    return "Mahogany"
