"""Dealer registry — the single source of truth for which dealers we pull from.

For Shopify dealers we just need the storefront URL: the generic
`shopify.fetch_products` function handles the rest via the public
`/products.json` endpoint.

For non-Shopify dealers we register the import path of a custom fetcher.

Each dealer also gets an `enabled` flag (default True). Disable a dealer here
to skip it in the runner without removing its code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Platform = Literal["shopify", "custom"]


@dataclass(frozen=True)
class DealerConfig:
    name: str
    platform: Platform
    url: str
    inventory_paths: tuple[str, ...] = ()
    fetcher: str | None = None  # dotted import path for custom dealers, e.g. "gibson_price.ingest.dealers.custom.gruhn:fetch"
    enabled: bool = True
    notes: str = ""
    brand_focus: tuple[str, ...] = field(default_factory=tuple)


REGISTRY: tuple[DealerConfig, ...] = (
    DealerConfig(
        name="carter_vintage",
        platform="shopify",
        url="https://cartervintage.com",
        inventory_paths=("/shop/category/acoustic-guitars",),
        notes="Carter Vintage Guitars (Nashville). Acquired Norman's in 2024.",
        brand_focus=("Gibson", "Martin", "Guild"),
    ),
    DealerConfig(
        name="normans_rare",
        platform="shopify",
        url="https://normansrareguitars.com",
        notes="Norman's Rare Guitars (Tarzana, CA). Owned by Carter Vintage as of 2024.",
        brand_focus=("Gibson", "Martin", "Fender"),
    ),
    DealerConfig(
        name="emerald_city",
        platform="shopify",
        url="https://emeraldcityguitars.com",
        notes="Emerald City Guitars (Seattle).",
        brand_focus=("Gibson", "Martin", "Guild"),
    ),
    DealerConfig(
        name="imperial_vintage",
        platform="shopify",
        url="https://imperialvintageguitars.com",
        notes="Imperial Vintage Guitars (Los Angeles).",
        brand_focus=("Gibson", "Martin"),
    ),
    DealerConfig(
        name="wildwood",
        platform="shopify",
        url="https://wildwoodguitars.com",
        notes="Wildwood Guitars (Louisville, CO). Boutique/new mostly, some vintage.",
        brand_focus=("Gibson", "Martin"),
    ),
    DealerConfig(
        name="gruhn",
        platform="custom",
        url="https://guitars.com",
        fetcher="gibson_price.ingest.dealers.custom.gruhn:fetch",
        notes="Gruhn Guitars (Nashville). Classic CMS, custom parser.",
        brand_focus=("Gibson", "Martin", "Guild", "Gretsch"),
    ),
    DealerConfig(
        name="elderly",
        platform="custom",
        url="https://www.elderly.com",
        fetcher="gibson_price.ingest.dealers.custom.elderly:fetch",
        notes="Elderly Instruments (Lansing, MI). Custom CMS with structured fields.",
        brand_focus=("Gibson", "Martin", "Guild"),
    ),
    DealerConfig(
        name="music_emporium",
        platform="custom",
        url="https://www.themusicemporium.com",
        fetcher="gibson_price.ingest.dealers.custom.music_emporium:fetch",
        notes="The Music Emporium (Lexington, MA). Magento.",
        brand_focus=("Gibson", "Martin", "Guild"),
    ),
    DealerConfig(
        name="vintage_and_rare",
        platform="custom",
        url="https://www.vintageandrare.com",
        fetcher="gibson_price.ingest.dealers.custom.vintage_and_rare:fetch",
        notes="Aggregator: indexes listings from many independent dealers worldwide.",
        brand_focus=("Gibson", "Martin", "Guild", "Gretsch"),
    ),
)


def enabled_dealers() -> list[DealerConfig]:
    return [d for d in REGISTRY if d.enabled]


def by_name(name: str) -> DealerConfig | None:
    for d in REGISTRY:
        if d.name == name:
            return d
    return None
