"""Vintage acoustic guitar pricing predictor — Gibson-focused hedonic ML."""

__version__ = "0.1.0"

from gibson_price.schema import (
    FeatureRow,
    GuitarListing,
    PricePrediction,
)

__all__ = ["FeatureRow", "GuitarListing", "PricePrediction", "__version__"]
