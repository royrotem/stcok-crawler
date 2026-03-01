"""High-level insight generation.

Combines data from all modules to produce actionable insights
and a unified market overview.
"""

from datetime import datetime

from loguru import logger

from src.analysis.sensitivity import compute_all_sensitivities
from src.engine.sectors import load_sectors, get_sector_exposure_matrix
from src.engine.transmission import TRANSMISSION_CHANNELS
from src.ingestion.news_sentiment import get_sector_sentiment_summary
from src.models.database import SessionLocal, MarketSnapshot, MacroIndicator
from sqlalchemy import desc


def generate_market_overview() -> dict:
    """Generate a comprehensive market overview combining all data sources.

    This is the main dashboard view that answers: "What's happening right now?"
    """
    db = SessionLocal()
    try:
        # Get latest market snapshots
        indices = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.market == "INDEX")
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(10)
            .all()
        )

        commodities = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.market == "COMMODITY")
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(5)
            .all()
        )

        currencies = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.market == "CURRENCY")
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(5)
            .all()
        )

        # Get latest macro indicators
        macro = (
            db.query(MacroIndicator)
            .order_by(desc(MacroIndicator.timestamp))
            .limit(10)
            .all()
        )

        # Get sentiment summary
        sentiment = get_sector_sentiment_summary()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "global_indices": [
                {
                    "symbol": idx.symbol,
                    "name": idx.name,
                    "price": idx.price,
                    "change_pct": idx.change_pct,
                }
                for idx in indices
            ],
            "commodities": [
                {
                    "symbol": c.symbol,
                    "name": c.name,
                    "price": c.price,
                    "change_pct": c.change_pct,
                }
                for c in commodities
            ],
            "currencies": [
                {
                    "symbol": c.symbol,
                    "name": c.name,
                    "price": c.price,
                    "change_pct": c.change_pct,
                }
                for c in currencies
            ],
            "macro_indicators": [
                {
                    "name": m.indicator_name,
                    "value": m.value,
                    "previous": m.previous_value,
                    "source": m.source,
                }
                for m in macro
            ],
            "sector_sentiment": sentiment,
        }
    finally:
        db.close()


def generate_sector_heatmap_data() -> dict:
    """Generate data for the TASE sector heatmap visualization.

    Returns sector-level aggregated data with change percentages and
    global impact context.
    """
    db = SessionLocal()
    config = load_sectors()

    try:
        sectors_data = []

        for sector_key, sector_info in config["sectors"].items():
            symbols = sector_info.get("symbols", [])

            # Get latest prices for this sector's stocks
            stock_data = []
            for sym in symbols:
                snap = (
                    db.query(MarketSnapshot)
                    .filter(MarketSnapshot.symbol == sym)
                    .order_by(desc(MarketSnapshot.timestamp))
                    .first()
                )
                if snap:
                    stock_data.append({
                        "symbol": snap.symbol,
                        "price": snap.price,
                        "change_pct": snap.change_pct or 0,
                    })

            if not stock_data:
                continue

            changes = [s["change_pct"] for s in stock_data]
            avg_change = sum(changes) / len(changes)

            sorted_stocks = sorted(stock_data, key=lambda x: x["change_pct"], reverse=True)

            sectors_data.append({
                "sector": sector_key,
                "name_en": sector_info["name_en"],
                "name_he": sector_info["name_he"],
                "avg_change_pct": round(avg_change, 2),
                "stock_count": len(stock_data),
                "top_gainers": [s["symbol"] for s in sorted_stocks[:2] if s["change_pct"] > 0],
                "top_losers": [s["symbol"] for s in sorted_stocks[-2:] if s["change_pct"] < 0],
                "stocks": stock_data,
                "global_factors": sector_info.get("global_sensitivity", []),
            })

        sectors_data.sort(key=lambda x: x["avg_change_pct"], reverse=True)

        # Generate global context summary
        global_context = _generate_global_context(db)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "sectors": sectors_data,
            "global_context": global_context,
        }

    finally:
        db.close()


def generate_timeline_events(limit: int = 50) -> list[dict]:
    """Generate a unified timeline of global and local events.

    Combines market data, macro events, and sentiment into a single
    chronological timeline.
    """
    db = SessionLocal()
    events = []

    try:
        # Significant market moves
        snapshots = (
            db.query(MarketSnapshot)
            .filter(
                (MarketSnapshot.change_pct > 2.0) | (MarketSnapshot.change_pct < -2.0)
            )
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(20)
            .all()
        )

        for snap in snapshots:
            events.append({
                "timestamp": snap.timestamp.isoformat(),
                "event_type": "market_move",
                "title": f"{snap.name or snap.symbol}: {snap.change_pct:+.1f}%",
                "description": f"{snap.symbol} moved {snap.change_pct:+.1f}% to {snap.price}",
                "impact_score": min(1.0, abs(snap.change_pct) / 10),
                "related_symbols": [snap.symbol],
                "market": snap.market,
            })

        # Macro indicator changes
        macros = (
            db.query(MacroIndicator)
            .order_by(desc(MacroIndicator.timestamp))
            .limit(10)
            .all()
        )

        for m in macros:
            if m.previous_value and m.previous_value != 0:
                change_pct = ((m.value - m.previous_value) / abs(m.previous_value)) * 100
            else:
                change_pct = 0

            events.append({
                "timestamp": m.timestamp.isoformat(),
                "event_type": "macro",
                "title": f"{m.indicator_name}: {m.value}",
                "description": f"{m.indicator_name} at {m.value} (prev: {m.previous_value})",
                "impact_score": min(1.0, abs(change_pct) / 5) if change_pct else 0,
                "related_symbols": [],
                "source": m.source,
            })

        # Sort all events by timestamp
        events.sort(key=lambda x: x["timestamp"], reverse=True)
        return events[:limit]

    finally:
        db.close()


def _generate_global_context(db) -> str:
    """Generate a text summary of current global market conditions."""
    sp500 = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == "^GSPC")
        .order_by(desc(MarketSnapshot.timestamp))
        .first()
    )

    nasdaq = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == "^IXIC")
        .order_by(desc(MarketSnapshot.timestamp))
        .first()
    )

    oil = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == "CL=F")
        .order_by(desc(MarketSnapshot.timestamp))
        .first()
    )

    parts = []
    if sp500:
        direction = "עלה" if (sp500.change_pct or 0) > 0 else "ירד"
        parts.append(f"S&P 500 {direction} ב-{abs(sp500.change_pct or 0):.1f}%")

    if nasdaq:
        direction = "עלה" if (nasdaq.change_pct or 0) > 0 else "ירד"
        parts.append(f"נאסד\"ק {direction} ב-{abs(nasdaq.change_pct or 0):.1f}%")

    if oil:
        parts.append(f"נפט WTI ב-${oil.price:.1f}")

    if parts:
        return "סיכום גלובלי: " + ", ".join(parts) + "."
    return "אין מידע גלובלי עדכני."
