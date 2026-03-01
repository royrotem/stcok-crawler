"""Causal alert generation system.

Generates "smart" alerts that explain WHY something happened,
not just WHAT happened. Uses transmission engine data and
sentiment analysis to provide causal context.
"""

from datetime import datetime

from loguru import logger

from src.engine.sectors import load_sectors
from src.engine.transmission import explain_price_movement, TRANSMISSION_CHANNELS
from src.ingestion.news_sentiment import get_sector_sentiment_summary
from src.models.database import Alert, MarketSnapshot, SessionLocal
from sqlalchemy import desc


def generate_price_alerts(threshold_pct: float = 2.0) -> list[Alert]:
    """Scan recent market data for significant price movements and generate causal alerts.

    Args:
        threshold_pct: Minimum absolute price change to trigger an alert.

    Returns:
        List of Alert objects ready for database storage.
    """
    db = SessionLocal()
    alerts = []

    try:
        # Get latest TASE snapshots
        snapshots = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.market == "TASE")
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(100)
            .all()
        )

        for snap in snapshots:
            if snap.change_pct is None:
                continue
            if abs(snap.change_pct) < threshold_pct:
                continue

            # Generate causal explanation
            explanation = explain_price_movement(snap.symbol, snap.change_pct)

            severity = "info"
            if abs(snap.change_pct) >= 5.0:
                severity = "critical"
            elif abs(snap.change_pct) >= 3.0:
                severity = "warning"

            direction = "עולה" if snap.change_pct > 0 else "יורדת"

            alert = Alert(
                alert_type="causal",
                severity=severity,
                title=f"{snap.symbol} {direction} ב-{abs(snap.change_pct):.1f}%",
                description=explanation,
                related_symbols=snap.symbol,
                cause_event=_find_likely_cause(snap),
                timestamp=datetime.utcnow(),
            )
            alerts.append(alert)

    finally:
        db.close()

    return alerts


def generate_global_impact_alerts() -> list[Alert]:
    """Generate alerts when global events are likely to impact TASE.

    Monitors overnight US market moves and generates preemptive alerts
    before TASE opens.
    """
    db = SessionLocal()
    alerts = []

    try:
        # Check overnight US market moves
        us_indices = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.market == "INDEX")
            .filter(MarketSnapshot.symbol.in_(["^GSPC", "^IXIC", "^DJI"]))
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(3)
            .all()
        )

        significant_moves = [idx for idx in us_indices if idx.change_pct and abs(idx.change_pct) > 1.0]

        if significant_moves:
            config = load_sectors()

            for idx in significant_moves:
                direction = "עלה" if idx.change_pct > 0 else "ירד"
                severity = "warning" if abs(idx.change_pct) > 2.0 else "info"

                # Determine which TASE sectors are most affected
                affected_sectors = []
                if idx.symbol in ("^IXIC",):
                    affected_sectors = ["tech", "pharma"]
                elif idx.symbol in ("^GSPC", "^DJI"):
                    affected_sectors = ["banks", "tech", "insurance"]

                sector_names = []
                for s in affected_sectors:
                    info = config["sectors"].get(s, {})
                    sector_names.append(info.get("name_he", s))

                alert = Alert(
                    alert_type="causal",
                    severity=severity,
                    title=f"{idx.name} {direction} ב-{abs(idx.change_pct):.1f}% - השפעה צפויה על הבורסה",
                    description=(
                        f"מדד {idx.name} {direction} ב-{abs(idx.change_pct):.1f}% "
                        f"במסחר בוול סטריט. "
                        f"סקטורים שצפויים להיות מושפעים בבורסת ת\"א: "
                        f"{', '.join(sector_names)}."
                    ),
                    related_symbols=",".join(
                        sym
                        for s in affected_sectors
                        for sym in config["sectors"].get(s, {}).get("symbols", [])[:2]
                    ),
                    cause_event=f"{idx.name} {idx.change_pct:+.1f}%",
                    timestamp=datetime.utcnow(),
                )
                alerts.append(alert)

        # Check commodity moves
        commodities = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.market == "COMMODITY")
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(5)
            .all()
        )

        for comm in commodities:
            if comm.change_pct and abs(comm.change_pct) > 3.0:
                direction = "עלה" if comm.change_pct > 0 else "ירד"

                alert = Alert(
                    alert_type="causal",
                    severity="warning",
                    title=f"{comm.name}: {direction} ב-{abs(comm.change_pct):.1f}%",
                    description=(
                        f"מחיר {comm.name} {direction} ב-{abs(comm.change_pct):.1f}%. "
                        f"שינוי משמעותי שעשוי להשפיע על סקטור האנרגיה ועלויות הייצור בבורסת ת\"א."
                    ),
                    related_symbols=comm.symbol,
                    cause_event=f"{comm.name} {comm.change_pct:+.1f}%",
                    timestamp=datetime.utcnow(),
                )
                alerts.append(alert)

    finally:
        db.close()

    return alerts


def generate_sentiment_alerts() -> list[Alert]:
    """Generate alerts based on extreme sentiment shifts."""
    alerts = []

    try:
        sentiment = get_sector_sentiment_summary()

        for sector, data in sentiment.items():
            avg_sent = data.get("avg_sentiment", 0)
            count = data.get("article_count", 0)

            if count < 3:
                continue

            if avg_sent < -0.3:
                alert = Alert(
                    alert_type="causal",
                    severity="warning",
                    title=f"סנטימנט שלילי חריג בסקטור {sector}",
                    description=(
                        f"ניתוח {count} כתבות מצביע על סנטימנט שלילי חריג "
                        f"(ציון: {avg_sent:.2f}) בסקטור {sector}. "
                        f"זה עשוי להצביע על לחץ מכירות צפוי."
                    ),
                    related_symbols=sector,
                    cause_event=f"Negative sentiment: {avg_sent:.2f}",
                    timestamp=datetime.utcnow(),
                )
                alerts.append(alert)
            elif avg_sent > 0.3:
                alert = Alert(
                    alert_type="causal",
                    severity="info",
                    title=f"סנטימנט חיובי חריג בסקטור {sector}",
                    description=(
                        f"ניתוח {count} כתבות מצביע על סנטימנט חיובי חריג "
                        f"(ציון: {avg_sent:.2f}) בסקטור {sector}. "
                        f"זה עשוי להצביע על מומנטום חיובי."
                    ),
                    related_symbols=sector,
                    cause_event=f"Positive sentiment: {avg_sent:.2f}",
                    timestamp=datetime.utcnow(),
                )
                alerts.append(alert)

    except Exception as e:
        logger.error(f"Error generating sentiment alerts: {e}")

    return alerts


def save_alerts(alerts: list[Alert]):
    """Persist alerts to database."""
    if not alerts:
        return

    db = SessionLocal()
    try:
        db.add_all(alerts)
        db.commit()
        logger.info(f"Saved {len(alerts)} alerts")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving alerts: {e}")
    finally:
        db.close()


def get_recent_alerts(limit: int = 20) -> list[dict]:
    """Get the most recent alerts for display."""
    db = SessionLocal()
    try:
        alerts = (
            db.query(Alert)
            .order_by(desc(Alert.timestamp))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": a.id,
                "type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "description": a.description,
                "related_symbols": a.related_symbols,
                "cause": a.cause_event,
                "timestamp": a.timestamp.isoformat(),
                "is_read": bool(a.is_read),
            }
            for a in alerts
        ]
    finally:
        db.close()


def run_alert_generation():
    """Run all alert generators and save results."""
    logger.info("Generating alerts...")

    all_alerts = []
    all_alerts.extend(generate_price_alerts())
    all_alerts.extend(generate_global_impact_alerts())
    all_alerts.extend(generate_sentiment_alerts())

    save_alerts(all_alerts)
    logger.info(f"Alert generation complete: {len(all_alerts)} alerts")
    return all_alerts


def _find_likely_cause(snapshot: MarketSnapshot) -> str:
    """Attempt to determine the most likely cause for a price movement."""
    config = load_sectors()

    # Find sector
    for sector_key, sector_info in config["sectors"].items():
        if snapshot.symbol in sector_info.get("symbols", []):
            factors = sector_info.get("global_sensitivity", [])
            if factors:
                return f"Sector sensitivity: {', '.join(factors)}"

    return "Market-wide movement"
