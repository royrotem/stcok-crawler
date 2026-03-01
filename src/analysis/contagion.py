"""Contagion analysis module.

Analyzes whether a crisis or significant event in one market/sector
could spread (contagion) to the Israeli market.
"""

from loguru import logger

from src.engine.sectors import load_sectors


# Predefined contagion scenarios based on historical patterns
CONTAGION_TEMPLATES = {
    "us_banking_crisis": {
        "trigger": "US Regional Banking Crisis",
        "trigger_he": "משבר בנקים אזוריים בארה\"ב",
        "transmission_channels": [
            "Direct confidence contagion to Israeli bank stocks",
            "Credit spread widening affects borrowing costs",
            "Risk-off sentiment reduces investment in Israeli equities",
            "Potential BOI response may affect rate trajectory",
        ],
        "affected_sectors": {
            "banks": {"risk": "high", "reason": "Direct sector correlation and confidence spillover"},
            "real_estate": {"risk": "high", "reason": "Credit tightening raises mortgage costs"},
            "insurance": {"risk": "medium", "reason": "Investment portfolio losses"},
            "tech": {"risk": "medium", "reason": "General risk-off sentiment"},
            "retail": {"risk": "low", "reason": "Indirect via consumer confidence"},
        },
    },
    "oil_shock": {
        "trigger": "Oil Price Spike (>20% increase)",
        "trigger_he": "זינוק במחירי הנפט (עלייה של מעל 20%)",
        "transmission_channels": [
            "Direct input cost increase for energy-dependent industries",
            "Inflationary pressure leads to rate hike expectations",
            "Transportation and logistics cost increase",
            "Benefits Israeli gas producers",
        ],
        "affected_sectors": {
            "energy": {"risk": "positive", "reason": "Israeli gas producers benefit from higher energy prices"},
            "retail": {"risk": "high", "reason": "Higher transportation and import costs, consumer squeeze"},
            "real_estate": {"risk": "medium", "reason": "Construction cost increase, inflation pressure"},
            "banks": {"risk": "medium", "reason": "Inflation may trigger rate changes"},
            "tech": {"risk": "low", "reason": "Minimal direct exposure"},
        },
    },
    "fed_rate_hike": {
        "trigger": "Unexpected Fed Rate Hike",
        "trigger_he": "העלאת ריבית מפתיעה של הפד",
        "transmission_channels": [
            "Higher US yields attract capital away from emerging/small markets",
            "BOI likely to follow with rate adjustment",
            "Strengthening USD hurts importers, helps exporters",
            "Growth stocks re-rated on higher discount rates",
        ],
        "affected_sectors": {
            "real_estate": {"risk": "high", "reason": "Higher rates directly increase mortgage and financing costs"},
            "tech": {"risk": "high", "reason": "Growth stock valuations compressed by higher rates"},
            "banks": {"risk": "medium", "reason": "Higher NIM but potential credit quality deterioration"},
            "insurance": {"risk": "positive", "reason": "Higher yields benefit investment portfolios"},
            "retail": {"risk": "medium", "reason": "Consumer spending pressured by higher rates"},
        },
    },
    "geopolitical_escalation": {
        "trigger": "Regional Geopolitical Escalation",
        "trigger_he": "הסלמה גיאופוליטית באזור",
        "transmission_channels": [
            "Direct risk premium increase on Israeli assets",
            "Shekel weakening against major currencies",
            "Defense spending increase benefits defense sector",
            "Capital flight from risk assets",
            "Tourism and consumer confidence decline",
        ],
        "affected_sectors": {
            "defense": {"risk": "positive", "reason": "Increased defense spending and export demand"},
            "banks": {"risk": "high", "reason": "Risk premium increase, potential credit deterioration"},
            "real_estate": {"risk": "high", "reason": "Construction disruption, demand uncertainty"},
            "tech": {"risk": "high", "reason": "Risk-off sentiment, but some benefit from shekel weakness"},
            "retail": {"risk": "high", "reason": "Consumer confidence collapse, supply chain disruption"},
            "insurance": {"risk": "high", "reason": "Potential claims increase, portfolio losses"},
        },
    },
    "china_slowdown": {
        "trigger": "China Economic Slowdown",
        "trigger_he": "האטה כלכלית בסין",
        "transmission_channels": [
            "Reduced global demand for commodities",
            "Supply chain disruptions",
            "General risk-off in emerging markets",
            "Lower oil demand reduces energy prices",
        ],
        "affected_sectors": {
            "tech": {"risk": "medium", "reason": "Global demand reduction, but limited direct China exposure"},
            "energy": {"risk": "high", "reason": "Reduced global oil/gas demand"},
            "banks": {"risk": "low", "reason": "Limited direct China exposure"},
            "real_estate": {"risk": "low", "reason": "Mostly domestic market"},
        },
    },
    "european_debt_crisis": {
        "trigger": "European Debt Crisis Resurgence",
        "trigger_he": "חידוש משבר החוב האירופי",
        "transmission_channels": [
            "EUR/ILS exchange rate volatility",
            "European bank exposure affects global banking confidence",
            "Reduced EU trade demand",
            "Risk premium increase for non-US developed markets",
        ],
        "affected_sectors": {
            "banks": {"risk": "medium", "reason": "Confidence contagion from European banking stress"},
            "pharma": {"risk": "medium", "reason": "European market access and pricing pressure"},
            "tech": {"risk": "low", "reason": "US-focused, limited European exposure"},
            "retail": {"risk": "medium", "reason": "EUR weakness affects import pricing"},
        },
    },
}


def analyze_contagion(scenario_key: str) -> dict:
    """Run a contagion analysis for a predefined crisis scenario.

    Args:
        scenario_key: One of the keys in CONTAGION_TEMPLATES

    Returns:
        Detailed contagion analysis with risk levels per sector.
    """
    if scenario_key not in CONTAGION_TEMPLATES:
        return {
            "error": f"Unknown scenario: {scenario_key}",
            "available_scenarios": list(CONTAGION_TEMPLATES.keys()),
        }

    template = CONTAGION_TEMPLATES[scenario_key]
    config = load_sectors()

    # Enrich with stock symbols per sector
    enriched_sectors = {}
    overall_risk_scores = []

    risk_values = {"positive": 0.2, "low": 0.3, "medium": 0.6, "high": 0.9}

    for sector_key, impact in template["affected_sectors"].items():
        sector_info = config["sectors"].get(sector_key, {})
        risk_score = risk_values.get(impact["risk"], 0.5)
        overall_risk_scores.append(risk_score)

        enriched_sectors[sector_key] = {
            "name": sector_info.get("name_en", sector_key),
            "name_he": sector_info.get("name_he", sector_key),
            "risk_level": impact["risk"],
            "risk_score": risk_score,
            "reason": impact["reason"],
            "affected_stocks": sector_info.get("symbols", []),
        }

    # Overall risk level
    avg_risk = sum(overall_risk_scores) / len(overall_risk_scores) if overall_risk_scores else 0
    if avg_risk >= 0.7:
        overall_level = "high"
    elif avg_risk >= 0.4:
        overall_level = "medium"
    else:
        overall_level = "low"

    return {
        "scenario": scenario_key,
        "trigger_event": template["trigger"],
        "trigger_event_he": template["trigger_he"],
        "risk_level": overall_level,
        "risk_score": round(avg_risk, 2),
        "transmission_channels": template["transmission_channels"],
        "affected_sectors": enriched_sectors,
        "explanation": _generate_explanation(template, overall_level),
    }


def analyze_custom_contagion(
    trigger_description: str,
    affected_factors: list[str],
) -> dict:
    """Analyze contagion for a custom event based on the factors it affects.

    Args:
        trigger_description: Free-text description of the event
        affected_factors: List of factors affected (e.g., ["oil_price", "geopolitical", "vix"])

    Returns:
        Analysis of which TASE sectors would be impacted.
    """
    from src.engine.sectors import map_global_factor_to_sectors

    all_affected = {}

    for factor in affected_factors:
        sectors = map_global_factor_to_sectors(factor)
        for s in sectors:
            key = s["sector"]
            if key not in all_affected:
                all_affected[key] = {
                    "sector": key,
                    "name": s["name_en"],
                    "factors_count": 0,
                    "directions": [],
                    "symbols": s["symbols"],
                }
            all_affected[key]["factors_count"] += 1
            all_affected[key]["directions"].append(s["direction"])

    # Score based on how many factors hit each sector
    for sector in all_affected.values():
        sector["exposure_score"] = round(sector["factors_count"] / len(affected_factors), 2)

    sorted_sectors = sorted(all_affected.values(), key=lambda x: x["exposure_score"], reverse=True)

    return {
        "trigger_event": trigger_description,
        "affected_factors": affected_factors,
        "sector_impacts": sorted_sectors,
    }


def get_available_scenarios() -> list[dict]:
    """List all available contagion scenarios."""
    return [
        {
            "key": key,
            "trigger": template["trigger"],
            "trigger_he": template["trigger_he"],
            "sector_count": len(template["affected_sectors"]),
        }
        for key, template in CONTAGION_TEMPLATES.items()
    ]


def _generate_explanation(template: dict, overall_level: str) -> str:
    """Generate a Hebrew explanation of the contagion analysis."""
    high_risk = [
        sector for sector, impact in template["affected_sectors"].items()
        if impact["risk"] == "high"
    ]

    positive = [
        sector for sector, impact in template["affected_sectors"].items()
        if impact["risk"] == "positive"
    ]

    explanation = f"ניתוח הדבקה: {template['trigger_he']}. "

    if overall_level == "high":
        explanation += "רמת הסיכון הכוללת גבוהה. "
    elif overall_level == "medium":
        explanation += "רמת הסיכון הכוללת בינונית. "
    else:
        explanation += "רמת הסיכון הכוללת נמוכה. "

    if high_risk:
        explanation += f"הסקטורים בסיכון הגבוה ביותר: {', '.join(high_risk)}. "

    if positive:
        explanation += f"סקטורים שעשויים דווקא להרוויח: {', '.join(positive)}. "

    explanation += f"ערוצי הדבקה מרכזיים: {len(template['transmission_channels'])}."

    return explanation
