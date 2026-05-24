"""Dealer registry — the single source of truth for which dealers we pull from.

Three platform strategies, in order of preference:
  - shopify: hit `/products.json` (one generic client; covers any Shopify storefront)
  - generic: sitemap.xml + JSON-LD (one generic client; covers most modern e-comm)
  - custom: bespoke per-site parser when the above fail

A fourth `common_crawl` field on any dealer enables historical backfill from
the Common Crawl archive — works without ever touching the dealer's servers.

Adding a Shopify dealer or a JSON-LD-publishing dealer is a one-line change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Platform = Literal["shopify", "generic", "custom"]


@dataclass(frozen=True)
class DealerConfig:
    name: str
    platform: Platform
    url: str
    inventory_paths: tuple[str, ...] = ()
    product_path: str = "/products/"  # Path fragment that identifies a product URL
    fetcher: str | None = None        # Dotted import path for `custom` dealers
    enabled: bool = True
    notes: str = ""
    brand_focus: tuple[str, ...] = field(default_factory=tuple)
    common_crawl_domain: str | None = None  # If set, enables historical backfill via CC


REGISTRY: tuple[DealerConfig, ...] = (
    # ----- Shopify storefronts (handled by generic /products.json client) -----
    DealerConfig(
        name="carter_vintage", platform="shopify",
        url="https://cartervintage.com",
        inventory_paths=("/shop/category/acoustic-guitars",),
        notes="Carter Vintage Guitars (Nashville). Acquired Norman's in 2024.",
        brand_focus=("Gibson", "Martin", "Guild"),
        common_crawl_domain="cartervintage.com",
    ),
    DealerConfig(
        name="normans_rare", platform="shopify",
        url="https://normansrareguitars.com",
        notes="Norman's Rare Guitars (Tarzana, CA). Owned by Carter Vintage as of 2024.",
        brand_focus=("Gibson", "Martin", "Fender"),
        common_crawl_domain="normansrareguitars.com",
    ),
    DealerConfig(
        name="emerald_city", platform="shopify",
        url="https://emeraldcityguitars.com",
        notes="Emerald City Guitars (Seattle).",
        brand_focus=("Gibson", "Martin", "Guild"),
        common_crawl_domain="emeraldcityguitars.com",
    ),
    DealerConfig(
        name="imperial_vintage", platform="shopify",
        url="https://imperialvintageguitars.com",
        notes="Imperial Vintage Guitars (Los Angeles).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="imperialvintageguitars.com",
    ),
    DealerConfig(
        name="wildwood", platform="shopify",
        url="https://wildwoodguitars.com",
        notes="Wildwood Guitars (Louisville, CO).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="wildwoodguitars.com",
    ),
    DealerConfig(
        name="dream_guitars", platform="shopify",
        url="https://www.dreamguitars.com",
        notes="Dream Guitars (Weaverville, NC).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="dreamguitars.com",
    ),
    DealerConfig(
        name="retrofret", platform="shopify",
        url="https://retrofret.com",
        notes="Retrofret Vintage Guitars (Brooklyn).",
        brand_focus=("Gibson", "Martin", "Guild", "Gretsch"),
        common_crawl_domain="retrofret.com",
    ),
    DealerConfig(
        name="lark_street", platform="shopify",
        url="https://www.larkstreetmusic.com",
        notes="Lark Street Music (Teaneck, NJ).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="larkstreetmusic.com",
    ),

    # ----- Generic (sitemap + JSON-LD) -----
    DealerConfig(
        name="mass_street", platform="generic",
        url="https://www.massstreetmusic.com",
        product_path="/product/",
        notes="Mass Street Music (Lawrence, KS).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="massstreetmusic.com",
    ),
    DealerConfig(
        name="twelfth_fret", platform="generic",
        url="https://12fret.com",
        product_path="/product/",
        notes="The Twelfth Fret (Toronto). CAD prices auto-skipped.",
        brand_focus=("Gibson", "Martin", "Guild"),
        common_crawl_domain="12fret.com",
    ),
    DealerConfig(
        name="tr_crandall", platform="generic",
        url="https://www.trcrandallguitars.com",
        notes="TR Crandall Guitars (NYC).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="trcrandallguitars.com",
    ),
    DealerConfig(
        name="folkway", platform="generic",
        url="https://www.folkwaymusic.com",
        product_path="/product/",
        notes="Folkway Music (Guelph, ON).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="folkwaymusic.com",
    ),
    DealerConfig(
        name="vintage_instruments_philly", platform="generic",
        url="https://www.vintageinstruments.com",
        product_path="/product/",
        notes="Vintage Instruments Philadelphia (Fred Oster).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="vintageinstruments.com",
    ),
    DealerConfig(
        name="acoustic_vibes", platform="generic",
        url="https://acousticvibesmusic.com",
        notes="Acoustic Vibes Music (Tempe, AZ).",
        brand_focus=("Gibson", "Martin", "Guild"),
        common_crawl_domain="acousticvibesmusic.com",
    ),
    DealerConfig(
        name="mahars_vintage", platform="generic",
        url="https://www.maharsvintageguitars.com",
        notes="Mahar's Vintage Guitars (Schenectady, NY).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="maharsvintageguitars.com",
    ),
    DealerConfig(
        name="joes_vintage", platform="generic",
        url="https://www.joesvintageguitarsaz.com",
        notes="Joe's Vintage Guitars (Phoenix).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="joesvintageguitarsaz.com",
    ),
    DealerConfig(
        name="true_vintage_guitar", platform="generic",
        url="https://truevintageguitar.com",
        notes="True Vintage Guitar (NJ).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="truevintageguitar.com",
    ),
    DealerConfig(
        name="edgewater", platform="generic",
        url="https://edgewaterguitars.com",
        notes="Edgewater Guitars (Edgewater, NJ).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="edgewaterguitars.com",
    ),
    DealerConfig(
        name="cme_vintage", platform="generic",
        url="https://www.chicagomusicexchange.com",
        product_path="/products/",
        notes="Chicago Music Exchange (vintage section).",
        brand_focus=("Gibson", "Martin"),
        common_crawl_domain="chicagomusicexchange.com",
    ),

    # ----- Custom (bespoke parser when JSON-LD/sitemap don't work) -----
    DealerConfig(
        name="gruhn", platform="custom",
        url="https://guitars.com",
        fetcher="gibson_price.ingest.dealers.custom.gruhn:fetch",
        notes="Gruhn Guitars (Nashville). Classic CMS, custom parser.",
        brand_focus=("Gibson", "Martin", "Guild", "Gretsch"),
        common_crawl_domain="guitars.com",
    ),
    DealerConfig(
        name="elderly", platform="custom",
        url="https://www.elderly.com",
        fetcher="gibson_price.ingest.dealers.custom.elderly:fetch",
        notes="Elderly Instruments (Lansing, MI). Structured serial fields.",
        brand_focus=("Gibson", "Martin", "Guild"),
        common_crawl_domain="elderly.com",
    ),
    DealerConfig(
        name="music_emporium", platform="custom",
        url="https://www.themusicemporium.com",
        fetcher="gibson_price.ingest.dealers.custom.music_emporium:fetch",
        notes="The Music Emporium (Lexington, MA).",
        brand_focus=("Gibson", "Martin", "Guild"),
        common_crawl_domain="themusicemporium.com",
    ),
    DealerConfig(
        name="vintage_and_rare", platform="custom",
        url="https://www.vintageandrare.com",
        fetcher="gibson_price.ingest.dealers.custom.vintage_and_rare:fetch",
        notes="Multi-dealer aggregator (dozens of independent dealers worldwide).",
        brand_focus=("Gibson", "Martin", "Guild", "Gretsch"),
        common_crawl_domain="vintageandrare.com",
    ),
)


def enabled_dealers() -> list[DealerConfig]:
    return [d for d in REGISTRY if d.enabled]


def by_name(name: str) -> DealerConfig | None:
    for d in REGISTRY:
        if d.name == name:
            return d
    return None


def dealers_with_cc() -> list[DealerConfig]:
    """Subset that has Common Crawl backfill enabled."""
    return [d for d in REGISTRY if d.enabled and d.common_crawl_domain]

