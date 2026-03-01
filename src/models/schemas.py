"""Pydantic schemas for API request/response models."""

from datetime import datetime

from pydantic import BaseModel


# --- Market Data ---

class MarketSnapshotResponse(BaseModel):
    symbol: str
    name: str | None
    price: float
    change_pct: float | None
    volume: float | None
    market: str
    sector: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}


class SectorHeatmapItem(BaseModel):
    sector: str
    avg_change_pct: float
    top_gainers: list[str]
    top_losers: list[str]
    global_impact_score: float  # -1.0 to 1.0


class HeatmapResponse(BaseModel):
    timestamp: datetime
    sectors: list[SectorHeatmapItem]
    global_context: str  # brief summary of overnight events


# --- Macro ---

class MacroIndicatorResponse(BaseModel):
    indicator_name: str
    value: float
    previous_value: float | None
    change_pct: float | None
    source: str
    timestamp: datetime

    model_config = {"from_attributes": True}


# --- Sentiment ---

class SentimentResponse(BaseModel):
    headline: str
    source: str | None
    sentiment_score: float
    sector: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}


class SectorSentiment(BaseModel):
    sector: str
    avg_sentiment: float
    article_count: int
    trend: str  # "improving", "declining", "stable"


# --- Correlation ---

class CorrelationPair(BaseModel):
    symbol_a: str
    symbol_b: str
    correlation: float
    window_days: int

    model_config = {"from_attributes": True}


class TransmissionLink(BaseModel):
    global_event: str
    local_impact: str
    affected_sectors: list[str]
    estimated_impact_pct: float
    confidence: float


# --- Analysis / Insights ---

class SensitivityScore(BaseModel):
    symbol: str
    name: str | None
    global_sensitivity: float  # 0.0 to 1.0
    top_factors: list[str]


class ScenarioRequest(BaseModel):
    variable: str  # e.g., "oil_price", "usd_ils", "fed_rate"
    change_pct: float  # e.g., 10.0 for +10%


class ScenarioResult(BaseModel):
    variable: str
    change_pct: float
    winners: list[dict]  # [{symbol, name, expected_impact_pct}]
    losers: list[dict]
    explanation: str


class ContagionAnalysis(BaseModel):
    trigger_event: str
    risk_level: str  # "low", "medium", "high"
    affected_local_sectors: list[str]
    transmission_channels: list[str]
    explanation: str


# --- Alerts ---

class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    description: str
    related_symbols: str | None
    cause_event: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}


# --- Timeline ---

class TimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str  # "global", "local", "macro", "sentiment"
    title: str
    description: str
    impact_score: float | None  # -1.0 to 1.0
    related_symbols: list[str]
