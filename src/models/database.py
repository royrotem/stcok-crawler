"""SQLAlchemy database models for market data storage."""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


class MarketSnapshot(Base):
    """Point-in-time snapshot of a market index or asset price."""

    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), index=True, nullable=False)
    name = Column(String(200))
    price = Column(Float, nullable=False)
    change_pct = Column(Float)
    volume = Column(Float)
    market = Column(String(20))  # "US", "TASE", "COMMODITY", "CRYPTO"
    sector = Column(String(50))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class MacroIndicator(Base):
    """Macroeconomic indicator data point."""

    __tablename__ = "macro_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    indicator_name = Column(String(100), index=True, nullable=False)
    value = Column(Float, nullable=False)
    previous_value = Column(Float)
    source = Column(String(50))  # "FRED", "BOI", "ECB"
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class SentimentRecord(Base):
    """Sentiment analysis result from a news source."""

    __tablename__ = "sentiment_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    headline = Column(Text, nullable=False)
    source = Column(String(100))
    url = Column(Text)
    sentiment_score = Column(Float)  # -1.0 to 1.0
    sector = Column(String(50))
    related_symbols = Column(Text)  # comma-separated symbols
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class CorrelationRecord(Base):
    """Computed correlation between two assets/indicators."""

    __tablename__ = "correlation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_a = Column(String(20), index=True, nullable=False)
    symbol_b = Column(String(20), index=True, nullable=False)
    correlation = Column(Float, nullable=False)
    window_days = Column(Integer, default=30)
    timestamp = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """Generated alert with causal explanation."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), nullable=False)  # "causal", "threshold", "scenario"
    severity = Column(String(20), default="info")  # "info", "warning", "critical"
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    related_symbols = Column(Text)
    cause_event = Column(Text)
    is_read = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
