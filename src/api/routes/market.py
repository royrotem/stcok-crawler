"""Market data API routes."""

from fastapi import APIRouter, Query
from sqlalchemy import desc

from src.ingestion.market_data import (
    fetch_dual_listed_spread,
    fetch_historical,
    run_full_market_ingestion,
)
from src.models.database import MarketSnapshot, SessionLocal

router = APIRouter()


@router.get("/snapshots")
async def get_market_snapshots(
    market: str | None = Query(None, description="Filter by market: INDEX, TASE, COMMODITY, CURRENCY"),
    sector: str | None = Query(None, description="Filter by sector (for TASE)"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get the latest market snapshots."""
    db = SessionLocal()
    try:
        query = db.query(MarketSnapshot).order_by(desc(MarketSnapshot.timestamp))

        if market:
            query = query.filter(MarketSnapshot.market == market.upper())
        if sector:
            query = query.filter(MarketSnapshot.sector == sector)

        results = query.limit(limit).all()
        return [
            {
                "symbol": r.symbol,
                "name": r.name,
                "price": r.price,
                "change_pct": r.change_pct,
                "volume": r.volume,
                "market": r.market,
                "sector": r.sector,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in results
        ]
    finally:
        db.close()


@router.get("/historical/{symbol}")
async def get_historical_data(
    symbol: str,
    period: str = Query("3mo", description="Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y"),
):
    """Get historical price data for a specific symbol."""
    df = fetch_historical(symbol, period)
    if df.empty:
        return {"error": f"No data found for {symbol}", "data": []}

    return {
        "symbol": symbol,
        "period": period,
        "data": [
            {
                "date": str(idx.date()),
                "open": round(row["Open"], 4),
                "high": round(row["High"], 4),
                "low": round(row["Low"], 4),
                "close": round(row["Close"], 4),
                "volume": int(row["Volume"]) if row["Volume"] > 0 else None,
            }
            for idx, row in df.iterrows()
        ],
    }


@router.get("/dual-listed")
async def get_dual_listed():
    """Get price comparison for dual-listed Israeli companies (US vs TASE)."""
    return fetch_dual_listed_spread()


@router.post("/refresh")
async def trigger_refresh():
    """Manually trigger a full market data refresh."""
    snapshots = run_full_market_ingestion()
    return {"status": "ok", "snapshots_count": len(snapshots)}
