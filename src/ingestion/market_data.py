"""Market data ingestion via Yahoo Finance.

Handles global indices (S&P 500, NASDAQ), TASE stocks, commodities, and currencies.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from loguru import logger

from src.models.database import MarketSnapshot, SessionLocal

SECTOR_FILE = Path(__file__).parent.parent.parent / "data" / "tase_sectors.json"


def _load_sector_config() -> dict:
    with open(SECTOR_FILE) as f:
        return json.load(f)


def fetch_global_indices() -> list[MarketSnapshot]:
    """Fetch latest data for major global indices."""
    config = _load_sector_config()
    symbols = {k: v for k, v in config["global_indices"].items()}
    return _fetch_symbols(symbols, market="INDEX")


def fetch_commodities() -> list[MarketSnapshot]:
    """Fetch latest commodity prices (oil, gold, natural gas)."""
    config = _load_sector_config()
    symbols = {k: v for k, v in config["commodities"].items()}
    return _fetch_symbols(symbols, market="COMMODITY")


def fetch_currencies() -> list[MarketSnapshot]:
    """Fetch latest exchange rates (USD/ILS, EUR/ILS)."""
    config = _load_sector_config()
    symbols = {k: v for k, v in config["currencies"].items()}
    return _fetch_symbols(symbols, market="CURRENCY")


def fetch_tase_stocks() -> list[MarketSnapshot]:
    """Fetch latest TASE stock prices organized by sector."""
    config = _load_sector_config()
    snapshots = []

    for sector_key, sector_info in config["sectors"].items():
        symbol_list = sector_info["symbols"]
        for sym in symbol_list:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                hist = ticker.history(period="2d")

                if hist.empty:
                    logger.warning(f"No data for {sym}")
                    continue

                current_price = hist["Close"].iloc[-1]
                change_pct = 0.0
                if len(hist) >= 2:
                    prev_price = hist["Close"].iloc[-2]
                    change_pct = ((current_price - prev_price) / prev_price) * 100

                snapshot = MarketSnapshot(
                    symbol=sym,
                    name=sector_info.get("name_en", sym),
                    price=round(float(current_price), 2),
                    change_pct=round(change_pct, 2),
                    volume=float(hist["Volume"].iloc[-1]) if "Volume" in hist else None,
                    market="TASE",
                    sector=sector_key,
                    timestamp=datetime.utcnow(),
                )
                snapshots.append(snapshot)
            except Exception as e:
                logger.error(f"Error fetching {sym}: {e}")

    return snapshots


def fetch_historical(symbol: str, period: str = "3mo") -> pd.DataFrame:
    """Fetch historical price data for a single symbol.

    Args:
        symbol: Ticker symbol (e.g., "AAPL", "LUMI.TA", "^GSPC")
        period: yfinance period string (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)

    Returns:
        DataFrame with Date, Open, High, Low, Close, Volume columns.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        return hist
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {e}")
        return pd.DataFrame()


def fetch_dual_listed_spread() -> list[dict]:
    """Compare prices of dual-listed Israeli companies between US and TASE.

    Returns spread data that can indicate arbitrage opportunities or
    market sentiment divergence.
    """
    config = _load_sector_config()
    dual = config.get("dual_listed", {}).get("companies", [])
    spreads = []

    for company in dual:
        try:
            us_ticker = yf.Ticker(company["us"])
            tase_ticker = yf.Ticker(company["tase"])

            us_hist = us_ticker.history(period="1d")
            tase_hist = tase_ticker.history(period="1d")

            if us_hist.empty or tase_hist.empty:
                continue

            us_price = float(us_hist["Close"].iloc[-1])
            tase_price = float(tase_hist["Close"].iloc[-1])

            spreads.append({
                "name": company["name"],
                "us_symbol": company["us"],
                "tase_symbol": company["tase"],
                "us_price_usd": round(us_price, 2),
                "tase_price_ils": round(tase_price, 2),
                "us_change_pct": round(
                    ((us_price - float(us_hist["Open"].iloc[-1])) / float(us_hist["Open"].iloc[-1])) * 100, 2
                ),
            })
        except Exception as e:
            logger.error(f"Error fetching dual-listed {company['name']}: {e}")

    return spreads


def _fetch_symbols(symbols: dict, market: str) -> list[MarketSnapshot]:
    """Generic fetcher for a dict of {key: {symbol, name}} entries."""
    snapshots = []

    for key, info in symbols.items():
        sym = info["symbol"]
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="2d")

            if hist.empty:
                logger.warning(f"No data for {sym}")
                continue

            current_price = hist["Close"].iloc[-1]
            change_pct = 0.0
            if len(hist) >= 2:
                prev_price = hist["Close"].iloc[-2]
                change_pct = ((current_price - prev_price) / prev_price) * 100

            snapshot = MarketSnapshot(
                symbol=sym,
                name=info["name"],
                price=round(float(current_price), 4),
                change_pct=round(change_pct, 2),
                volume=float(hist["Volume"].iloc[-1]) if "Volume" in hist and hist["Volume"].iloc[-1] > 0 else None,
                market=market,
                sector=None,
                timestamp=datetime.utcnow(),
            )
            snapshots.append(snapshot)
        except Exception as e:
            logger.error(f"Error fetching {sym}: {e}")

    return snapshots


def save_snapshots(snapshots: list[MarketSnapshot]):
    """Persist a list of snapshots to the database."""
    if not snapshots:
        return

    db = SessionLocal()
    try:
        db.add_all(snapshots)
        db.commit()
        logger.info(f"Saved {len(snapshots)} market snapshots")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving snapshots: {e}")
    finally:
        db.close()


def run_full_market_ingestion():
    """Run a complete ingestion cycle for all market data."""
    logger.info("Starting full market data ingestion...")

    all_snapshots = []
    all_snapshots.extend(fetch_global_indices())
    all_snapshots.extend(fetch_commodities())
    all_snapshots.extend(fetch_currencies())
    all_snapshots.extend(fetch_tase_stocks())

    save_snapshots(all_snapshots)
    logger.info(f"Full ingestion complete: {len(all_snapshots)} snapshots")
    return all_snapshots
