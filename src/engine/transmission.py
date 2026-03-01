"""Transmission mechanism analysis.

Models how global events propagate to local (TASE) markets through
various channels: interest rates, exchange rates, commodity prices,
and sentiment contagion.
"""

from loguru import logger

from src.engine.correlation import compute_correlation
from src.engine.sectors import load_sectors, map_global_factor_to_sectors
from src.ingestion.news_sentiment import get_sector_sentiment_summary


# Predefined transmission channels with estimated lag and strength
TRANSMISSION_CHANNELS = {
    "interest_rate": {
        "name": "Interest Rate Channel",
        "name_he": "ערוץ הריבית",
        "description": "Changes in US/global interest rates affect Israeli borrowing costs, "
                       "real estate valuations, and bank profitability",
        "lag_hours": 0,  # Immediate impact via expectations
        "affected_sectors": ["banks", "real_estate", "insurance"],
        "indicators": ["fed_rate", "boi_rate", "us_10y_yield"],
    },
    "exchange_rate": {
        "name": "Exchange Rate Channel",
        "name_he": "ערוץ שער החליפין",
        "description": "USD/ILS movements directly impact exporters (positive) and importers (negative)",
        "lag_hours": 0,
        "affected_sectors": ["tech", "pharma", "defense", "retail"],
        "indicators": ["usd_ils"],
    },
    "commodity": {
        "name": "Commodity Price Channel",
        "name_he": "ערוץ מחירי הסחורות",
        "description": "Oil and commodity price swings directly affect energy companies "
                       "and indirectly affect transportation and manufacturing costs",
        "lag_hours": 0,
        "affected_sectors": ["energy", "retail"],
        "indicators": ["oil_price", "natural_gas"],
    },
    "equity_sentiment": {
        "name": "Equity Sentiment Channel",
        "name_he": "ערוץ סנטימנט המניות",
        "description": "Wall Street overnight moves set the tone for TASE opening. "
                       "Dual-listed stocks transmit US sentiment directly",
        "lag_hours": 12,  # Overnight transmission
        "affected_sectors": ["tech"],
        "indicators": ["nasdaq", "sp500"],
    },
    "risk_appetite": {
        "name": "Risk Appetite Channel",
        "name_he": "ערוץ תיאבון הסיכון",
        "description": "VIX spikes and risk-off sentiment in global markets lead to "
                       "selling pressure in small/emerging markets including TASE",
        "lag_hours": 0,
        "affected_sectors": ["tech", "real_estate", "banks"],
        "indicators": ["vix"],
    },
    "geopolitical": {
        "name": "Geopolitical Channel",
        "name_he": "ערוץ גיאופוליטי",
        "description": "Regional instability, sanctions, or conflict escalation directly "
                       "impacts Israeli defense stocks and overall market risk premium",
        "lag_hours": 0,
        "affected_sectors": ["defense", "banks", "real_estate", "tech"],
        "indicators": ["geopolitical"],
    },
}


def analyze_overnight_impact(us_market_changes: dict) -> list[dict]:
    """Analyze how US overnight market changes will likely impact TASE opening.

    Args:
        us_market_changes: Dict with keys like "sp500_change_pct", "nasdaq_change_pct",
                          "oil_change_pct", "vix_change_pct", "usd_ils_change_pct"

    Returns:
        List of expected impacts per TASE sector.
    """
    impacts = []

    # Transmission weights (estimated from historical patterns)
    weights = {
        "tech": {
            "nasdaq": 0.7,
            "sp500": 0.3,
            "vix": -0.2,
            "usd_ils": 0.15,
        },
        "banks": {
            "sp500": 0.3,
            "vix": -0.25,
            "fed_rate_signal": 0.2,
        },
        "real_estate": {
            "sp500": 0.2,
            "vix": -0.15,
            "fed_rate_signal": -0.3,
        },
        "energy": {
            "oil": 0.6,
            "sp500": 0.15,
        },
        "pharma": {
            "nasdaq": 0.3,
            "sp500": 0.2,
            "usd_ils": 0.2,
        },
        "insurance": {
            "sp500": 0.2,
            "vix": -0.15,
        },
        "retail": {
            "sp500": 0.2,
            "oil": -0.1,
            "usd_ils": -0.15,
        },
        "defense": {
            "geopolitical_risk": 0.4,
            "sp500": 0.1,
            "usd_ils": 0.15,
        },
    }

    # Map input keys to weight keys
    change_mapping = {
        "sp500_change_pct": "sp500",
        "nasdaq_change_pct": "nasdaq",
        "oil_change_pct": "oil",
        "vix_change_pct": "vix",
        "usd_ils_change_pct": "usd_ils",
    }

    for sector, sector_weights in weights.items():
        expected_impact = 0.0
        contributing_factors = []

        for input_key, weight_key in change_mapping.items():
            if input_key in us_market_changes and weight_key in sector_weights:
                change = us_market_changes[input_key]
                weight = sector_weights[weight_key]
                contribution = change * weight
                expected_impact += contribution

                if abs(contribution) > 0.05:
                    contributing_factors.append({
                        "factor": weight_key,
                        "change_pct": round(change, 2),
                        "weight": weight,
                        "contribution": round(contribution, 2),
                    })

        impacts.append({
            "sector": sector,
            "expected_impact_pct": round(expected_impact, 2),
            "contributing_factors": contributing_factors,
            "confidence": min(0.9, 0.3 + 0.1 * len(contributing_factors)),
        })

    # Sort by absolute expected impact
    impacts.sort(key=lambda x: abs(x["expected_impact_pct"]), reverse=True)
    return impacts


def get_transmission_report() -> dict:
    """Generate a comprehensive transmission analysis report.

    Combines correlation data, sentiment, and sector analysis into
    a unified report of how global conditions are affecting local markets.
    """
    sentiment_summary = get_sector_sentiment_summary()
    config = load_sectors()

    report = {
        "channels": [],
        "sector_status": {},
        "key_risks": [],
    }

    # Analyze each transmission channel
    for channel_key, channel_info in TRANSMISSION_CHANNELS.items():
        channel_report = {
            "name": channel_info["name"],
            "name_he": channel_info["name_he"],
            "description": channel_info["description"],
            "affected_sectors": channel_info["affected_sectors"],
            "current_activity": "monitoring",
        }
        report["channels"].append(channel_report)

    # Per-sector status
    for sector_key, sector_info in config["sectors"].items():
        sentiment = sentiment_summary.get(sector_key, {})
        report["sector_status"][sector_key] = {
            "name": sector_info["name_en"],
            "name_he": sector_info["name_he"],
            "sentiment": sentiment.get("tone", "unknown"),
            "sentiment_score": sentiment.get("avg_sentiment", 0),
            "global_factors": sector_info.get("global_sensitivity", []),
        }

    return report


def explain_price_movement(symbol: str, change_pct: float) -> str:
    """Generate a causal explanation for a stock's price movement.

    This is the "smart alert" feature - instead of just saying a stock
    moved, explain WHY it likely moved based on:
    1. Sector sensitivity to global factors
    2. Recent global market changes
    3. News sentiment
    """
    config = load_sectors()

    # Find the sector for this symbol
    target_sector = None
    for sector_key, sector_info in config["sectors"].items():
        if symbol in sector_info.get("symbols", []):
            target_sector = sector_key
            break

    if not target_sector:
        return f"{symbol} changed by {change_pct:.1f}%"

    sector_info = config["sectors"][target_sector]
    factors = sector_info.get("global_sensitivity", [])

    direction = "עולה" if change_pct > 0 else "יורדת"
    abs_change = abs(change_pct)

    explanations = []

    if "nasdaq" in factors:
        explanations.append("שינויים במדד הנאסד\"ק שמשפיעים על סקטור הטכנולוגיה המקומי")
    if "fed_rate" in factors:
        explanations.append("ציפיות לשינוי בריבית הפד שמשפיעות על מחירי האשראי")
    if "oil_price" in factors:
        explanations.append("תנודות במחירי הנפט העולמי")
    if "usd_ils" in factors:
        explanations.append("שינויים בשער הדולר-שקל")
    if "geopolitical" in factors:
        explanations.append("התפתחויות גיאופוליטיות באזור")

    if not explanations:
        return f"{symbol} {direction} ב-{abs_change:.1f}%"

    causes = " ו".join(explanations[:2])
    return f"{symbol} {direction} ב-{abs_change:.1f}% - ככל הנראה בעקבות {causes}"
