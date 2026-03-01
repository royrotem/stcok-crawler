"""Analysis API routes - scenarios, sensitivity, contagion, correlations."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.analysis.contagion import (
    analyze_contagion,
    analyze_custom_contagion,
    get_available_scenarios as get_contagion_scenarios,
)
from src.analysis.scenarios import (
    get_available_scenarios as get_scenario_variables,
    run_multi_scenario,
    run_scenario,
)
from src.analysis.sensitivity import (
    compute_all_sensitivities,
    compute_stock_sensitivity,
    get_most_sensitive_stocks,
    get_least_sensitive_stocks,
)
from src.engine.correlation import (
    compute_correlation,
    compute_cross_market_matrix,
    compute_sector_correlations,
)
from src.engine.sectors import (
    get_all_sector_keys,
    get_sector_exposure_matrix,
    get_sector_symbols,
    map_global_factor_to_sectors,
)
from src.engine.transmission import (
    analyze_overnight_impact,
    get_transmission_report,
)

router = APIRouter()


# --- Scenarios ---

@router.get("/scenarios/variables")
async def list_scenario_variables():
    """List all available variables for what-if scenarios."""
    return get_scenario_variables()


@router.get("/scenarios/run")
async def run_what_if_scenario(
    variable: str = Query(..., description="Variable to change (e.g., oil_price, fed_rate)"),
    change_pct: float = Query(..., description="Percentage change to simulate (e.g., 10 for +10%)"),
):
    """Run a what-if scenario: 'What happens if X changes by Y%?'"""
    return run_scenario(variable, change_pct)


class MultiScenarioRequest(BaseModel):
    changes: dict[str, float]


@router.post("/scenarios/multi")
async def run_multi_scenario_analysis(request: MultiScenarioRequest):
    """Run a multi-variable scenario (e.g., oil +10% AND USD/ILS +3%)."""
    return run_multi_scenario(request.changes)


# --- Sensitivity ---

@router.get("/sensitivity")
async def get_all_sensitivity_scores():
    """Get global sensitivity scores for all tracked TASE stocks."""
    return compute_all_sensitivities()


@router.get("/sensitivity/{symbol}")
async def get_stock_sensitivity(symbol: str):
    """Get detailed sensitivity analysis for a single stock."""
    return compute_stock_sensitivity(symbol)


@router.get("/sensitivity/top/most-sensitive")
async def top_sensitive(n: int = Query(10, ge=1, le=50)):
    """Get the N stocks most sensitive to global events."""
    return get_most_sensitive_stocks(n)


@router.get("/sensitivity/top/least-sensitive")
async def least_sensitive(n: int = Query(10, ge=1, le=50)):
    """Get the N stocks least sensitive to global events (most 'local')."""
    return get_least_sensitive_stocks(n)


# --- Contagion ---

@router.get("/contagion/scenarios")
async def list_contagion_scenarios():
    """List all available contagion scenarios."""
    return get_contagion_scenarios()


@router.get("/contagion/analyze/{scenario_key}")
async def analyze_contagion_scenario(scenario_key: str):
    """Run contagion analysis for a predefined crisis scenario."""
    return analyze_contagion(scenario_key)


class CustomContagionRequest(BaseModel):
    trigger: str
    factors: list[str]


@router.post("/contagion/custom")
async def custom_contagion(request: CustomContagionRequest):
    """Analyze contagion for a custom event."""
    return analyze_custom_contagion(request.trigger, request.factors)


# --- Correlations ---

@router.get("/correlations/pair")
async def get_pair_correlation(
    symbol_a: str = Query(...),
    symbol_b: str = Query(...),
    period: str = Query("6mo"),
):
    """Compute correlation between two assets."""
    result = compute_correlation(symbol_a, symbol_b, period)
    if not result:
        return {"error": "Could not compute correlation"}
    return result


@router.get("/correlations/matrix")
async def get_cross_market_matrix(period: str = Query("6mo")):
    """Get the cross-market correlation matrix (global + local indices)."""
    return compute_cross_market_matrix(period)


@router.get("/correlations/sector/{sector_key}")
async def get_sector_benchmark_correlations(
    sector_key: str,
    benchmark: str = Query("^GSPC", description="Benchmark symbol"),
    period: str = Query("6mo"),
):
    """Compute correlations of sector stocks vs a global benchmark."""
    symbols = get_sector_symbols(sector_key)
    if not symbols:
        return {"error": f"Unknown sector: {sector_key}"}
    return compute_sector_correlations(symbols, benchmark, period)


# --- Sectors & Transmission ---

@router.get("/sectors")
async def list_sectors():
    """List all TASE sectors with their global exposure."""
    return get_sector_exposure_matrix()


@router.get("/sectors/factor/{factor}")
async def sectors_affected_by_factor(factor: str):
    """Find all TASE sectors affected by a specific global factor."""
    return map_global_factor_to_sectors(factor)


@router.get("/transmission/report")
async def transmission_report():
    """Get a comprehensive transmission analysis report."""
    return get_transmission_report()


@router.post("/transmission/overnight")
async def overnight_impact(changes: dict[str, float]):
    """Analyze expected TASE impact from overnight US market changes.

    Example body: {"sp500_change_pct": -2.0, "nasdaq_change_pct": -3.5, "oil_change_pct": 5.0}
    """
    return analyze_overnight_impact(changes)
