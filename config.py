"""Application configuration."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys (free tier)
    FRED_API_KEY: str = ""
    NEWS_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./data/market_data.db"

    # Scheduling intervals (seconds)
    MARKET_DATA_INTERVAL: int = 300  # 5 minutes
    NEWS_INTERVAL: int = 1800  # 30 minutes
    MACRO_DATA_INTERVAL: int = 3600  # 1 hour
    CORRELATION_INTERVAL: int = 900  # 15 minutes

    # Sentiment thresholds
    SENTIMENT_POSITIVE_THRESHOLD: float = 0.1
    SENTIMENT_NEGATIVE_THRESHOLD: float = -0.1

    # Alert thresholds
    PRICE_CHANGE_ALERT_THRESHOLD: float = 2.0  # percent
    CORRELATION_ALERT_THRESHOLD: float = 0.7

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
