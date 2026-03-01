"""Scenario modeling engine.

Implements "what-if" analysis: given a change in a global variable
(oil price, USD/ILS rate, Fed rate), estimate the impact on TASE stocks.
"""

import json
from pathlib import Path

from loguru import logger

SECTOR_FILE = Path(__file__).parent.parent.parent / "data" / "tase_sectors.json"

# Historical sensitivity coefficients (estimated from market studies)
# Format: {variable: {sector: beta_coefficient}}
# beta > 0 means positive correlation, beta < 0 means inverse
SCENARIO_BETAS = {
    "oil_price": {
        "energy": 0.65,
        "retail": -0.15,
        "banks": -0.05,
        "tech": -0.03,
        "real_estate": -0.08,
        "pharma": -0.02,
        "insurance": -0.03,
        "defense": 0.10,
    },
    "usd_ils": {
        "tech": 0.55,
        "pharma": 0.45,
        "defense": 0.40,
        "retail": -0.35,
        "banks": -0.10,
        "real_estate": -0.15,
        "energy": 0.05,
        "insurance": -0.05,
    },
    "fed_rate": {
        "real_estate": -0.70,
        "banks": 0.30,
        "insurance": 0.25,
        "tech": -0.40,
        "pharma": -0.15,
        "retail": -0.20,
        "energy": -0.05,
        "defense": -0.05,
    },
    "boi_rate": {
        "real_estate": -0.75,
        "banks": 0.35,
        "insurance": 0.30,
        "tech": -0.20,
        "retail": -0.25,
        "pharma": -0.05,
        "energy": -0.05,
        "defense": -0.05,
    },
    "nasdaq": {
        "tech": 0.80,
        "pharma": 0.30,
        "banks": 0.15,
        "real_estate": 0.10,
        "energy": 0.05,
        "insurance": 0.10,
        "retail": 0.10,
        "defense": 0.05,
    },
    "sp500": {
        "banks": 0.40,
        "tech": 0.50,
        "real_estate": 0.25,
        "insurance": 0.30,
        "retail": 0.20,
        "pharma": 0.25,
        "energy": 0.20,
        "defense": 0.10,
    },
    "gold": {
        "banks": 0.05,
        "real_estate": 0.10,
        "energy": 0.15,
        "tech": -0.05,
        "pharma": 0.02,
        "insurance": 0.05,
        "retail": -0.05,
        "defense": 0.10,
    },
    "vix": {
        "tech": -0.50,
        "banks": -0.35,
        "real_estate": -0.30,
        "insurance": -0.20,
        "pharma": -0.15,
        "retail": -0.20,
        "energy": -0.15,
        "defense": -0.10,
    },
    "inflation": {
        "real_estate": 0.15,
        "banks": 0.10,
        "retail": -0.30,
        "tech": -0.20,
        "energy": 0.20,
        "insurance": -0.10,
        "pharma": -0.10,
        "defense": 0.05,
    },
}

# Human-readable variable names
VARIABLE_NAMES = {
    "oil_price": {"en": "Oil Price (WTI)", "he": "מחיר הנפט"},
    "usd_ils": {"en": "USD/ILS Exchange Rate", "he": "שער הדולר-שקל"},
    "fed_rate": {"en": "Federal Funds Rate", "he": "ריבית הפד"},
    "boi_rate": {"en": "Bank of Israel Rate", "he": "ריבית בנק ישראל"},
    "nasdaq": {"en": "NASDAQ Index", "he": "מדד הנאסד\"ק"},
    "sp500": {"en": "S&P 500 Index", "he": "מדד S&P 500"},
    "gold": {"en": "Gold Price", "he": "מחיר הזהב"},
    "vix": {"en": "VIX (Volatility)", "he": "מדד הפחד (VIX)"},
    "inflation": {"en": "Inflation Rate", "he": "שיעור האינפלציה"},
}


def _load_sectors() -> dict:
    with open(SECTOR_FILE) as f:
        return json.load(f)


def run_scenario(variable: str, change_pct: float) -> dict:
    """Run a what-if scenario analysis.

    Example: "What happens to TASE stocks if oil price rises by 10%?"

    Args:
        variable: One of the keys in SCENARIO_BETAS
        change_pct: Percentage change to simulate (e.g., 10.0 for +10%)

    Returns:
        Scenario result with winners, losers, and detailed explanations.
    """
    if variable not in SCENARIO_BETAS:
        return {
            "error": f"Unknown variable: {variable}",
            "available_variables": list(SCENARIO_BETAS.keys()),
        }

    betas = SCENARIO_BETAS[variable]
    config = _load_sectors()
    var_name = VARIABLE_NAMES.get(variable, {})

    results = []

    for sector_key, beta in betas.items():
        expected_change = change_pct * beta
        sector_info = config["sectors"].get(sector_key, {})

        results.append({
            "sector": sector_key,
            "sector_name": sector_info.get("name_en", sector_key),
            "sector_name_he": sector_info.get("name_he", sector_key),
            "beta": beta,
            "expected_change_pct": round(expected_change, 2),
            "symbols": sector_info.get("symbols", []),
        })

    # Sort: most positive at top
    results.sort(key=lambda x: x["expected_change_pct"], reverse=True)

    winners = [r for r in results if r["expected_change_pct"] > 0]
    losers = [r for r in results if r["expected_change_pct"] < 0]

    direction = "עלייה" if change_pct > 0 else "ירידה"
    explanation = (
        f"סימולציה: {direction} של {abs(change_pct):.1f}% ב{var_name.get('he', variable)}. "
        f"{len(winners)} סקטורים צפויים להרוויח, "
        f"{len(losers)} סקטורים צפויים להיפגע."
    )

    if winners:
        top_winner = winners[0]
        explanation += (
            f" הסקטור שצפוי להרוויח ביותר: {top_winner['sector_name_he']} "
            f"(+{top_winner['expected_change_pct']:.1f}%)."
        )

    if losers:
        top_loser = losers[-1]
        explanation += (
            f" הסקטור שצפוי להיפגע ביותר: {top_loser['sector_name_he']} "
            f"({top_loser['expected_change_pct']:.1f}%)."
        )

    return {
        "variable": variable,
        "variable_name": var_name.get("en", variable),
        "variable_name_he": var_name.get("he", variable),
        "change_pct": change_pct,
        "winners": winners,
        "losers": losers,
        "explanation": explanation,
    }


def run_multi_scenario(changes: dict) -> dict:
    """Run a scenario with multiple simultaneous variable changes.

    Example: Oil +10% AND USD/ILS +3% at the same time.

    Args:
        changes: Dict of {variable: change_pct}

    Returns:
        Combined impact analysis across all sectors.
    """
    config = _load_sectors()
    sector_impacts = {}

    for variable, change_pct in changes.items():
        if variable not in SCENARIO_BETAS:
            continue

        betas = SCENARIO_BETAS[variable]
        for sector_key, beta in betas.items():
            if sector_key not in sector_impacts:
                sector_impacts[sector_key] = {
                    "sector": sector_key,
                    "sector_name": config["sectors"].get(sector_key, {}).get("name_en", sector_key),
                    "total_impact": 0.0,
                    "breakdown": [],
                }

            impact = change_pct * beta
            sector_impacts[sector_key]["total_impact"] += impact
            sector_impacts[sector_key]["breakdown"].append({
                "variable": variable,
                "change_pct": change_pct,
                "beta": beta,
                "contribution": round(impact, 2),
            })

    # Round totals
    for sector in sector_impacts.values():
        sector["total_impact"] = round(sector["total_impact"], 2)

    sorted_sectors = sorted(sector_impacts.values(), key=lambda x: x["total_impact"], reverse=True)

    return {
        "scenario_inputs": changes,
        "sector_impacts": sorted_sectors,
    }


def get_available_scenarios() -> list[dict]:
    """List all available scenario variables with descriptions."""
    return [
        {
            "variable": key,
            "name_en": VARIABLE_NAMES.get(key, {}).get("en", key),
            "name_he": VARIABLE_NAMES.get(key, {}).get("he", key),
            "affected_sectors": list(betas.keys()),
        }
        for key, betas in SCENARIO_BETAS.items()
    ]
