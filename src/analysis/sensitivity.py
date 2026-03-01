"""Sensitivity scoring for TASE stocks.

Assigns each stock a "global sensitivity score" (0.0 - 1.0) that indicates
how much it is influenced by global events vs. being purely local.
"""

import json
from pathlib import Path

from loguru import logger

from src.engine.correlation import compute_correlation

SECTOR_FILE = Path(__file__).parent.parent.parent / "data" / "tase_sectors.json"

# Base sensitivity scores by sector (prior knowledge)
SECTOR_BASE_SENSITIVITY = {
    "tech": 0.85,       # Dual-listed, highly global
    "pharma": 0.75,     # FDA-dependent, global markets
    "defense": 0.65,    # Geopolitical + export-driven
    "banks": 0.55,      # Some global exposure via rates
    "insurance": 0.50,  # Bond yield sensitive
    "energy": 0.60,     # Commodity price driven
    "real_estate": 0.45,  # Mostly local but rate-sensitive
    "retail": 0.35,     # Mostly local consumption
}

# Global benchmarks to measure correlation against
GLOBAL_BENCHMARKS = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "oil": "CL=F",
    "usd_ils": "USDILS=X",
}


def _load_sectors() -> dict:
    with open(SECTOR_FILE, encoding="utf-8") as f:
        return json.load(f)


def compute_stock_sensitivity(symbol: str, sector: str | None = None) -> dict:
    """Compute a global sensitivity score for a single stock.

    The score combines:
    1. Sector base sensitivity (prior knowledge)
    2. Actual correlation with global benchmarks (if computable)

    Args:
        symbol: TASE ticker symbol
        sector: Sector key (if known, saves a lookup)

    Returns:
        Dict with sensitivity score and contributing factors.
    """
    config = _load_sectors()

    # Find sector if not provided
    if not sector:
        for key, info in config["sectors"].items():
            if symbol in info.get("symbols", []):
                sector = key
                break

    base_score = SECTOR_BASE_SENSITIVITY.get(sector, 0.5)

    # Try to compute actual correlations
    correlations = {}
    for bench_name, bench_symbol in GLOBAL_BENCHMARKS.items():
        result = compute_correlation(symbol, bench_symbol, period="3mo")
        if result:
            correlations[bench_name] = abs(result["correlation"])

    # Blend base score with actual correlation data
    if correlations:
        avg_correlation = sum(correlations.values()) / len(correlations)
        # Weighted blend: 40% base, 60% actual
        final_score = 0.4 * base_score + 0.6 * avg_correlation
    else:
        final_score = base_score

    final_score = min(1.0, max(0.0, round(final_score, 3)))

    # Determine top factors
    sector_info = config["sectors"].get(sector, {})
    top_factors = sector_info.get("global_sensitivity", [])

    return {
        "symbol": symbol,
        "sector": sector,
        "global_sensitivity": final_score,
        "base_sector_score": base_score,
        "benchmark_correlations": correlations,
        "top_factors": top_factors,
        "interpretation": _interpret_score(final_score),
    }


def compute_all_sensitivities() -> list[dict]:
    """Compute sensitivity scores for all tracked TASE stocks.

    This uses only base sector scores (no API calls) for speed.
    Use compute_stock_sensitivity() for individual deep analysis.
    """
    config = _load_sectors()
    results = []

    for sector_key, sector_info in config["sectors"].items():
        base_score = SECTOR_BASE_SENSITIVITY.get(sector_key, 0.5)

        for symbol in sector_info.get("symbols", []):
            results.append({
                "symbol": symbol,
                "name": sector_info.get("name_en", ""),
                "sector": sector_key,
                "global_sensitivity": base_score,
                "top_factors": sector_info.get("global_sensitivity", []),
            })

    results.sort(key=lambda x: x["global_sensitivity"], reverse=True)
    return results


def get_most_sensitive_stocks(top_n: int = 10) -> list[dict]:
    """Get the N stocks with highest global sensitivity."""
    all_stocks = compute_all_sensitivities()
    return all_stocks[:top_n]


def get_least_sensitive_stocks(top_n: int = 10) -> list[dict]:
    """Get the N stocks with lowest global sensitivity (most 'local')."""
    all_stocks = compute_all_sensitivities()
    return all_stocks[-top_n:]


def _interpret_score(score: float) -> str:
    """Generate a human-readable interpretation of the sensitivity score."""
    if score >= 0.8:
        return "רגישות גבוהה מאוד - המניה מושפעת בצורה ישירה מאירועים גלובליים"
    elif score >= 0.6:
        return "רגישות גבוהה - השפעה משמעותית של שווקים עולמיים"
    elif score >= 0.4:
        return "רגישות בינונית - שילוב של גורמים מקומיים וגלובליים"
    elif score >= 0.2:
        return "רגישות נמוכה - מושפעת בעיקר מגורמים מקומיים"
    else:
        return "רגישות מינימלית - כמעט לא מושפעת מהשווקים העולמיים"
