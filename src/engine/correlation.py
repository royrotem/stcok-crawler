"""Correlation analysis engine.

Computes statistical correlations between global and local market data
to identify and quantify transmission channels.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

from src.models.database import CorrelationRecord, SessionLocal


def compute_correlation(symbol_a: str, symbol_b: str, period: str = "6mo") -> dict | None:
    """Compute the Pearson correlation between two assets' daily returns.

    Args:
        symbol_a: First ticker symbol
        symbol_b: Second ticker symbol
        period: Historical period to analyze

    Returns:
        Dict with correlation value and metadata, or None on failure.
    """
    try:
        data_a = yf.Ticker(symbol_a).history(period=period)["Close"]
        data_b = yf.Ticker(symbol_b).history(period=period)["Close"]

        if data_a.empty or data_b.empty:
            return None

        # Compute daily returns
        returns_a = data_a.pct_change().dropna()
        returns_b = data_b.pct_change().dropna()

        # Align dates
        aligned = pd.concat([returns_a, returns_b], axis=1, join="inner")
        aligned.columns = ["a", "b"]
        aligned = aligned.dropna()

        if len(aligned) < 10:
            return None

        corr = float(aligned["a"].corr(aligned["b"]))

        return {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "correlation": round(corr, 4),
            "data_points": len(aligned),
            "period": period,
        }

    except Exception as e:
        logger.error(f"Error computing correlation {symbol_a} vs {symbol_b}: {e}")
        return None


def compute_rolling_correlation(
    symbol_a: str, symbol_b: str, period: str = "1y", window: int = 30
) -> pd.DataFrame:
    """Compute rolling correlation to see how the relationship evolves over time.

    Args:
        symbol_a: First ticker symbol
        symbol_b: Second ticker symbol
        period: Historical period
        window: Rolling window in trading days

    Returns:
        DataFrame with date and rolling correlation values.
    """
    try:
        data_a = yf.Ticker(symbol_a).history(period=period)["Close"]
        data_b = yf.Ticker(symbol_b).history(period=period)["Close"]

        returns_a = data_a.pct_change().dropna()
        returns_b = data_b.pct_change().dropna()

        aligned = pd.concat([returns_a, returns_b], axis=1, join="inner")
        aligned.columns = ["a", "b"]
        aligned = aligned.dropna()

        rolling_corr = aligned["a"].rolling(window=window).corr(aligned["b"])
        result = pd.DataFrame({"date": rolling_corr.index, "correlation": rolling_corr.values})
        return result.dropna()

    except Exception as e:
        logger.error(f"Error computing rolling correlation: {e}")
        return pd.DataFrame()


def compute_sector_correlations(
    sector_symbols: list[str], benchmark: str = "^GSPC", period: str = "6mo"
) -> list[dict]:
    """Compute correlation of each stock in a sector against a global benchmark.

    Args:
        sector_symbols: List of TASE ticker symbols
        benchmark: Global benchmark symbol (default S&P 500)
        period: Historical period

    Returns:
        List of correlation results sorted by absolute correlation.
    """
    results = []

    for symbol in sector_symbols:
        result = compute_correlation(symbol, benchmark, period)
        if result:
            results.append(result)

    results.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return results


def compute_cross_market_matrix(period: str = "6mo") -> dict:
    """Compute a correlation matrix between key global and local indices.

    This is the core of the transmission analysis - it shows how tightly
    coupled different markets are.
    """
    symbols = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "TA-35": "TA35.TA",
        "Oil (WTI)": "CL=F",
        "Gold": "GC=F",
        "USD/ILS": "USDILS=X",
        "VIX": "^VIX",
    }

    # Fetch all historical data
    price_data = {}
    for name, symbol in symbols.items():
        try:
            data = yf.Ticker(symbol).history(period=period)["Close"]
            if not data.empty:
                price_data[name] = data.pct_change().dropna()
        except Exception as e:
            logger.error(f"Error fetching {name}: {e}")

    if len(price_data) < 2:
        return {}

    # Build aligned DataFrame
    df = pd.DataFrame(price_data)
    df = df.dropna()

    # Compute correlation matrix
    corr_matrix = df.corr()

    return {
        "matrix": corr_matrix.round(4).where(corr_matrix.notna(), other=None).to_dict(),
        "data_points": len(df),
        "period": period,
        "assets": list(price_data.keys()),
    }


def detect_correlation_shifts(
    symbol_a: str, symbol_b: str, period: str = "1y", window: int = 30, threshold: float = 0.3
) -> list[dict]:
    """Detect significant shifts in the correlation between two assets.

    A sudden change in correlation often signals a regime change or
    structural shift in the market relationship.
    """
    rolling = compute_rolling_correlation(symbol_a, symbol_b, period, window)
    if rolling.empty:
        return []

    shifts = []
    corr_values = rolling["correlation"].values
    dates = rolling["date"].values

    for i in range(1, len(corr_values)):
        change = abs(corr_values[i] - corr_values[i - 1])
        if change > threshold:
            shifts.append({
                "date": str(dates[i]),
                "previous_correlation": round(float(corr_values[i - 1]), 4),
                "new_correlation": round(float(corr_values[i]), 4),
                "change": round(float(change), 4),
                "direction": "strengthening" if corr_values[i] > corr_values[i - 1] else "weakening",
            })

    return shifts


def save_correlations(results: list[dict]):
    """Save correlation records to database."""
    db = SessionLocal()
    try:
        for r in results:
            record = CorrelationRecord(
                symbol_a=r["symbol_a"],
                symbol_b=r["symbol_b"],
                correlation=r["correlation"],
                window_days=r.get("data_points", 0),
                timestamp=datetime.utcnow(),
            )
            db.add(record)
        db.commit()
        logger.info(f"Saved {len(results)} correlation records")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving correlations: {e}")
    finally:
        db.close()
