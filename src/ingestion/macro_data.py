"""Macroeconomic data ingestion.

Fetches Fed rates, CPI, unemployment, and other macro indicators from FRED.
Also scrapes Bank of Israel rate decisions.
"""

from datetime import datetime

import pandas as pd
import requests
from loguru import logger

from config import settings
from src.models.database import MacroIndicator, SessionLocal

# Key FRED series IDs for our use case
FRED_SERIES = {
    "fed_rate": {
        "series_id": "FEDFUNDS",
        "name": "Federal Funds Rate",
    },
    "us_cpi": {
        "series_id": "CPIAUCSL",
        "name": "US Consumer Price Index",
    },
    "us_unemployment": {
        "series_id": "UNRATE",
        "name": "US Unemployment Rate",
    },
    "us_10y_yield": {
        "series_id": "DGS10",
        "name": "US 10-Year Treasury Yield",
    },
    "us_2y_yield": {
        "series_id": "DGS2",
        "name": "US 2-Year Treasury Yield",
    },
    "breakeven_inflation": {
        "series_id": "T10YIE",
        "name": "10-Year Breakeven Inflation Rate",
    },
    "us_gdp": {
        "series_id": "GDP",
        "name": "US GDP",
    },
    "consumer_sentiment": {
        "series_id": "UMCSENT",
        "name": "University of Michigan Consumer Sentiment",
    },
}

# Bank of Israel rate endpoint (publicly available)
BOI_RATE_URL = "https://www.boi.org.il/en/economic-roles/monetary-policy/interest-rate-decisions/"


def fetch_fred_series(series_id: str, limit: int = 5) -> pd.DataFrame:
    """Fetch a single FRED data series.

    Args:
        series_id: FRED series identifier (e.g., "FEDFUNDS")
        limit: Number of most recent observations

    Returns:
        DataFrame with date and value columns.
    """
    if not settings.FRED_API_KEY:
        logger.warning("FRED_API_KEY not set - skipping FRED data fetch")
        return pd.DataFrame()

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": settings.FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        observations = data.get("observations", [])
        if not observations:
            return pd.DataFrame()

        df = pd.DataFrame(observations)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        return df[["date", "value"]].dropna()

    except Exception as e:
        logger.error(f"Error fetching FRED series {series_id}: {e}")
        return pd.DataFrame()


def fetch_all_macro_indicators() -> list[MacroIndicator]:
    """Fetch all configured macro indicators from FRED."""
    indicators = []

    for key, config in FRED_SERIES.items():
        df = fetch_fred_series(config["series_id"], limit=2)
        if df.empty:
            continue

        current_value = float(df.iloc[0]["value"])
        previous_value = float(df.iloc[1]["value"]) if len(df) > 1 else None

        indicator = MacroIndicator(
            indicator_name=config["name"],
            value=current_value,
            previous_value=previous_value,
            source="FRED",
            timestamp=datetime.utcnow(),
        )
        indicators.append(indicator)
        logger.debug(f"Fetched {config['name']}: {current_value}")

    return indicators


def fetch_boi_rate() -> MacroIndicator | None:
    """Attempt to fetch the latest Bank of Israel interest rate.

    Uses a simple web scrape of the BOI public page.
    """
    try:
        resp = requests.get(BOI_RATE_URL, timeout=15)
        resp.raise_for_status()

        # The BOI page structure varies; we do best-effort parsing
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for rate value in the page content
        text = soup.get_text()
        # Simple heuristic: find percentage values near "interest rate"
        import re

        matches = re.findall(r"(\d+\.?\d*)\s*%", text)
        if matches:
            rate = float(matches[0])
            return MacroIndicator(
                indicator_name="Bank of Israel Interest Rate",
                value=rate,
                previous_value=None,
                source="BOI",
                timestamp=datetime.utcnow(),
            )
    except Exception as e:
        logger.error(f"Error fetching BOI rate: {e}")

    return None


def get_yield_curve_spread() -> dict | None:
    """Calculate the 10Y-2Y yield spread (recession indicator).

    A negative spread (inverted yield curve) is historically a strong
    recession predictor.
    """
    df_10y = fetch_fred_series("DGS10", limit=1)
    df_2y = fetch_fred_series("DGS2", limit=1)

    if df_10y.empty or df_2y.empty:
        return None

    yield_10y = float(df_10y.iloc[0]["value"])
    yield_2y = float(df_2y.iloc[0]["value"])
    spread = yield_10y - yield_2y

    return {
        "yield_10y": yield_10y,
        "yield_2y": yield_2y,
        "spread": round(spread, 3),
        "inverted": spread < 0,
        "signal": "recession_warning" if spread < 0 else "normal",
    }


def save_indicators(indicators: list[MacroIndicator]):
    """Persist macro indicators to the database."""
    if not indicators:
        return

    db = SessionLocal()
    try:
        db.add_all(indicators)
        db.commit()
        logger.info(f"Saved {len(indicators)} macro indicators")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving indicators: {e}")
    finally:
        db.close()


def run_macro_ingestion():
    """Run a full macro data ingestion cycle."""
    logger.info("Starting macro data ingestion...")

    indicators = fetch_all_macro_indicators()

    boi = fetch_boi_rate()
    if boi:
        indicators.append(boi)

    save_indicators(indicators)
    logger.info(f"Macro ingestion complete: {len(indicators)} indicators")
    return indicators
