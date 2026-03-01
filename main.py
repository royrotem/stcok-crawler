"""TASE Market Intelligence System - Entry Point.

Usage:
    python main.py              # Start the full server (API + scheduler + dashboard)
    python main.py --fetch      # Run a one-time data fetch without starting the server
"""

import sys

import uvicorn
from loguru import logger

from config import settings


def main():
    if "--fetch" in sys.argv:
        # One-time data fetch mode
        from src.models.database import init_db
        from src.ingestion.market_data import run_full_market_ingestion
        from src.ingestion.macro_data import run_macro_ingestion
        from src.ingestion.news_sentiment import run_sentiment_ingestion
        from src.alerts.causal_alerts import run_alert_generation

        logger.info("Running one-time data fetch...")
        init_db()

        snapshots = run_full_market_ingestion()
        logger.info(f"Market: {len(snapshots)} snapshots")

        indicators = run_macro_ingestion()
        logger.info(f"Macro: {len(indicators)} indicators")

        records = run_sentiment_ingestion()
        logger.info(f"Sentiment: {len(records)} records")

        alerts = run_alert_generation()
        logger.info(f"Alerts: {len(alerts)} generated")

        logger.info("One-time fetch complete.")
        return

    # Start the full server
    logger.info(f"Starting TASE Market Intelligence on {settings.HOST}:{settings.PORT}")
    logger.info("Dashboard: http://localhost:8000")
    logger.info("API docs: http://localhost:8000/docs")

    uvicorn.run(
        "src.api.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
