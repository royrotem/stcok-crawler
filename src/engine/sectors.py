"""Sector mapping and classification engine.

Manages the relationship between TASE sectors and their global sensitivity factors.
"""

import json
from pathlib import Path

from loguru import logger

SECTOR_FILE = Path(__file__).parent.parent.parent / "data" / "tase_sectors.json"


def load_sectors() -> dict:
    """Load the full sector configuration."""
    with open(SECTOR_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_sector_symbols(sector_key: str) -> list[str]:
    """Get all ticker symbols for a given TASE sector."""
    config = load_sectors()
    sector = config["sectors"].get(sector_key, {})
    return sector.get("symbols", [])


def get_sector_sensitivities(sector_key: str) -> list[str]:
    """Get the global factors that a sector is sensitive to."""
    config = load_sectors()
    sector = config["sectors"].get(sector_key, {})
    return sector.get("global_sensitivity", [])


def get_all_sector_keys() -> list[str]:
    """Get all available sector keys."""
    config = load_sectors()
    return list(config["sectors"].keys())


def map_global_factor_to_sectors(factor: str) -> list[dict]:
    """Given a global factor, find all TASE sectors affected by it.

    Args:
        factor: e.g., "fed_rate", "oil_price", "nasdaq", "geopolitical"

    Returns:
        List of dicts with sector info and expected impact direction.
    """
    config = load_sectors()
    affected = []

    # Impact direction heuristics based on factor type
    impact_map = {
        "fed_rate": {
            "banks": "mixed",  # Higher rates: good for NIM, bad for credit risk
            "real_estate": "negative",  # Higher rates = higher mortgage costs
            "insurance": "positive",  # Higher yields benefit investment portfolios
            "tech": "negative",  # Growth stocks suffer from rate hikes
        },
        "boi_rate": {
            "banks": "mixed",
            "real_estate": "negative",
            "insurance": "positive",
        },
        "oil_price": {
            "energy": "positive",
            "retail": "negative",  # Higher transportation/input costs
        },
        "nasdaq": {
            "tech": "positive",  # Strong correlation with dual-listed tech
        },
        "us_banks": {
            "banks": "correlated",
        },
        "geopolitical": {
            "defense": "positive",  # Defense spending increases
            "tech": "negative",  # Risk-off sentiment
            "real_estate": "negative",
        },
        "inflation": {
            "real_estate": "mixed",  # Asset appreciation vs higher costs
            "retail": "negative",  # Consumer spending drops
            "banks": "mixed",
        },
        "usd_ils": {
            "tech": "positive",  # Exporters benefit from strong dollar
            "pharma": "positive",
            "retail": "negative",  # Importers hurt by strong dollar
            "defense": "positive",
        },
        "consumer_confidence": {
            "retail": "positive",
            "banks": "positive",
        },
        "tech_sentiment": {
            "tech": "positive",
        },
        "credit_spreads": {
            "banks": "negative",  # Widening spreads = credit risk
            "real_estate": "negative",
        },
        "bond_yields": {
            "insurance": "positive",
            "banks": "mixed",
            "real_estate": "negative",
        },
    }

    factor_impacts = impact_map.get(factor, {})

    for sector_key, sector_info in config["sectors"].items():
        if factor in sector_info.get("global_sensitivity", []):
            direction = factor_impacts.get(sector_key, "unknown")
            affected.append({
                "sector": sector_key,
                "name_en": sector_info["name_en"],
                "name_he": sector_info["name_he"],
                "direction": direction,
                "symbols": sector_info["symbols"],
            })

    return affected


def get_sector_exposure_matrix() -> dict:
    """Build a complete matrix of which sectors are exposed to which factors.

    Returns a dict: {sector: [factors]} useful for comprehensive risk assessment.
    """
    config = load_sectors()
    matrix = {}

    for sector_key, sector_info in config["sectors"].items():
        matrix[sector_key] = {
            "name": sector_info["name_en"],
            "factors": sector_info.get("global_sensitivity", []),
            "symbol_count": len(sector_info.get("symbols", [])),
        }

    return matrix
