"""Pydantic schemas shared across ingest, features, and models.

GuitarListing is the raw record from any data source.
FeatureRow is the encoded row used for model training/inference.
PricePrediction is the structured output returned to the caller.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Brand = Literal["Gibson", "Martin", "Guild", "Gretsch", "Epiphone", "Other"]

Source = Literal[
    "reverb_api",
    "reverb_scrape",
    "heritage",
    "vg_guide",
    "dealer_archive",
    "dealer_shopify",
    "dealer_custom",
    "vintage_and_rare",
    "synthetic",
]

PriceConfidence = Literal["actual", "asking", "inferred"]

GIBSON_MODELS = {
    "J-45", "J-50", "J-160E", "J-180", "J-200", "SJ-200",
    "Hummingbird", "Dove", "Southern Jumbo", "Country Western",
    "L-00", "L-1", "L-2", "L-C", "Nick Lucas",
    "LG-0", "LG-1", "LG-2", "LG-3", "B-25", "B-45",
    "Advanced Jumbo", "Roy Smeck", "Everly Brothers",
}

MARTIN_MODELS = {"D-18", "D-21", "D-28", "D-35", "D-41", "D-45", "000-18", "000-28", "OM-28", "OM-45", "00-17"}
GUILD_MODELS = {"D-40", "D-50", "F-50", "F-30", "F-512", "F-412"}
GRETSCH_MODELS = {"Rancher", "Sun Valley", "Synchromatic"}


class ConditionGrade(int, Enum):
    """7-point ordinal scale, higher = better. Matches Vintage Guitar Price Guide conventions."""

    POOR = 1
    FAIR = 2
    GOOD = 3
    VERY_GOOD = 4
    VERY_GOOD_PLUS = 5
    EXCELLENT = 6
    MINT = 7


class GuitarListing(BaseModel):
    """Raw listing record from any source — minimally normalized, before feature encoding."""

    model_config = ConfigDict(extra="ignore")

    source: Source
    source_listing_id: str
    brand: Brand
    model_family: str
    year: int | None = None
    serial_number: str | None = None

    # Construction (often inferable from year+model if missing)
    factory: str | None = None
    top_wood: str | None = None
    back_sides_wood: str | None = None
    bracing_pattern: str | None = None
    bracing_scalloped: bool | None = None
    bridge_type: str | None = None
    tuner_type: str | None = None
    hide_glue_construction: bool | None = None

    # Cosmetics
    finish: str | None = None
    sunburst_pattern: str | None = None

    # Condition (granular)
    condition_grade: ConditionGrade | None = None
    headstock_repaired: bool = False
    neck_reset: bool = False
    refret: bool = False
    top_crack: bool = False
    side_crack: bool = False
    binding_shrinkage: bool = False

    # Originality
    refinished: bool = False
    replaced_tuners: bool = False
    replaced_bridge: bool = False
    replaced_pickup: bool = False
    replaced_pickguard: bool = False

    # Structural alterations — the "what if a 40s guitar was retopped in the 60s" cases.
    # These are much heavier deductions than a refinish or replaced tuners; the model
    # learns interactions (e.g. a retopped golden-era guitar loses the tonewood premium).
    top_replaced: bool = False
    top_replacement_year: int | None = None
    back_sides_replaced: bool = False
    back_sides_replacement_year: int | None = None
    neck_replaced: bool = False           # full neck swap (distinct from neck_reset)
    rebraced: bool = False                # bracing scheme rebuilt / replaced
    body_repaired_major: bool = False     # extensive body work (binding fully redone, etc.)
    electrified_aftermarket: bool = False # pickup/preamp installed after factory
    converted_cutaway: bool = False       # body modified to add a cutaway
    frankenguitar: bool = False           # parts assembled from multiple instruments

    # Provenance
    has_original_case: bool = False
    has_original_receipt: bool = False
    has_pre_war_certification: bool = False
    prior_famous_owner: bool = False

    # Listing metadata
    price_usd: float | None = None
    price_confidence: PriceConfidence | None = None
    is_sold: bool = False
    sold_date: date | None = None
    listing_date: date | None = None
    description: str | None = None
    url: str | None = None
    is_synthetic: bool = False

    # Quality control for parsed listings (regex 1.0, fuzzy 0.5-0.95, fallback < 0.5)
    extraction_confidence: float = 1.0


class FeatureRow(BaseModel):
    """Flat encoded row consumed by the model. All categoricals are strings; booleans are 0/1 ints."""

    model_config = ConfigDict(extra="forbid")

    # Identity
    brand: str
    model_family: str
    year: int
    era_segment: str
    factory: str
    body_shape: str

    # Construction
    top_wood: str
    back_sides_wood: str
    bracing_pattern: str
    bracing_scalloped: int
    bridge_type: str
    tuner_type: str
    hide_glue_construction: int

    # Cosmetics
    finish: str
    sunburst_pattern: str

    # Condition
    condition_grade: int
    headstock_repaired: int
    neck_reset: int
    refret: int
    top_crack: int
    side_crack: int
    binding_shrinkage: int

    # Originality
    refinished: int
    replaced_tuners: int
    replaced_bridge: int
    replaced_pickup: int
    replaced_pickguard: int

    # Structural alterations
    top_replaced: int
    top_replacement_era_distance: int     # |orig_year - replacement_year| in years; 0 if not replaced
    back_sides_replaced: int
    neck_replaced: int
    rebraced: int
    body_repaired_major: int
    electrified_aftermarket: int
    converted_cutaway: int
    frankenguitar: int

    # Provenance
    has_original_case: int
    has_original_receipt: int
    has_pre_war_certification: int
    prior_famous_owner: int

    # Metadata
    source: str
    sold_year: int = Field(description="Year of sale, used for time-trend modeling")


class ShapContribution(BaseModel):
    feature: str
    value: str
    contribution_usd: float


class PricePrediction(BaseModel):
    """Structured output from the predictor."""

    median_usd: float
    interval_low_usd: float = Field(description="Lower bound of the 80% prediction interval")
    interval_high_usd: float = Field(description="Upper bound of the 80% prediction interval")
    confidence_label: Literal["high", "medium", "low"]
    top_contributors: list[ShapContribution]
    natural_language_summary: str
    method: Literal["ml", "comps_fallback"]
    nearest_comps: list[dict] = Field(default_factory=list)


CATEGORICAL_FEATURES: tuple[str, ...] = (
    "brand",
    "model_family",
    "era_segment",
    "factory",
    "body_shape",
    "top_wood",
    "back_sides_wood",
    "bracing_pattern",
    "bridge_type",
    "tuner_type",
    "finish",
    "sunburst_pattern",
    "source",
)

NUMERIC_FEATURES: tuple[str, ...] = (
    "year",
    "sold_year",
    "condition_grade",
    "bracing_scalloped",
    "hide_glue_construction",
    "headstock_repaired",
    "neck_reset",
    "refret",
    "top_crack",
    "side_crack",
    "binding_shrinkage",
    "refinished",
    "replaced_tuners",
    "replaced_bridge",
    "replaced_pickup",
    "replaced_pickguard",
    "top_replaced",
    "top_replacement_era_distance",
    "back_sides_replaced",
    "neck_replaced",
    "rebraced",
    "body_repaired_major",
    "electrified_aftermarket",
    "converted_cutaway",
    "frankenguitar",
    "has_original_case",
    "has_original_receipt",
    "has_pre_war_certification",
    "prior_famous_owner",
)

ALL_FEATURES: tuple[str, ...] = CATEGORICAL_FEATURES + NUMERIC_FEATURES
