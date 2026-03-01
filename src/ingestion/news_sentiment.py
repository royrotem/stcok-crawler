"""News fetching and sentiment analysis.

Fetches headlines from financial news RSS feeds and NewsAPI,
then runs sentiment analysis to gauge market mood per sector.
"""

from datetime import datetime

import feedparser
import requests
from loguru import logger
from textblob import TextBlob

from config import settings
from src.models.database import SentimentRecord, SessionLocal

# Free RSS feeds for financial news
RSS_FEEDS = {
    "reuters_business": {
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "source": "Reuters",
    },
    "cnbc": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "source": "CNBC",
    },
    "marketwatch": {
        "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "source": "MarketWatch",
    },
    "yahoo_finance": {
        "url": "https://finance.yahoo.com/news/rssindex",
        "source": "Yahoo Finance",
    },
    "calcalist": {
        "url": "https://www.calcalist.co.il/GeneralRSS/0,16335,L-8,00.xml",
        "source": "Calcalist",
    },
    "globes": {
        "url": "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederV2?iID=2",
        "source": "Globes",
    },
}

# Keywords that map headlines to sectors
SECTOR_KEYWORDS = {
    "banks": ["bank", "banking", "credit", "loan", "mortgage", "financial services", "leumi", "discount", "hapoalim"],
    "tech": ["tech", "technology", "software", "cyber", "AI", "artificial intelligence", "semiconductor", "chip",
             "nvidia", "apple", "microsoft", "google", "meta", "check point", "nice systems", "cyberark", "monday.com"],
    "real_estate": ["real estate", "property", "housing", "construction", "REIT", "mortgage rate", "azrieli", "amot"],
    "energy": ["oil", "crude", "energy", "natural gas", "petroleum", "OPEC", "solar", "renewable"],
    "pharma": ["pharma", "pharmaceutical", "drug", "FDA", "biotech", "clinical trial", "teva", "generic"],
    "insurance": ["insurance", "insurer", "underwriting", "actuar", "harel", "migdal", "clal"],
    "retail": ["retail", "consumer", "shopping", "e-commerce", "store", "shufersal", "fox"],
    "defense": ["defense", "military", "weapon", "missile", "elbit", "rafael", "IAI"],
    "macro": ["interest rate", "inflation", "CPI", "GDP", "unemployment", "federal reserve", "fed",
              "bank of israel", "central bank", "monetary policy", "fiscal"],
    "geopolitical": ["war", "conflict", "sanctions", "trade war", "tariff", "geopolit", "tension",
                     "iran", "china", "russia", "ukraine", "middle east"],
}


def analyze_sentiment(text: str) -> float:
    """Analyze sentiment of a text string.

    Returns a score between -1.0 (very negative) and 1.0 (very positive).
    """
    blob = TextBlob(text)
    return round(blob.sentiment.polarity, 3)


def classify_sector(headline: str) -> str | None:
    """Classify a headline into a market sector based on keywords."""
    headline_lower = headline.lower()
    scores = {}

    for sector, keywords in SECTOR_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in headline_lower)
        if score > 0:
            scores[sector] = score

    if not scores:
        return None

    return max(scores, key=scores.get)


def find_related_symbols(headline: str) -> str:
    """Find stock symbols mentioned or implied in a headline."""
    headline_lower = headline.lower()
    symbols = []

    symbol_keywords = {
        "TEVA.TA": ["teva"],
        "CHKP.TA": ["check point", "checkpoint"],
        "NICE.TA": ["nice systems", "nice ltd"],
        "CYBR.TA": ["cyberark"],
        "LUMI.TA": ["leumi", "bank leumi"],
        "DSCT.TA": ["discount bank"],
        "ESLT.TA": ["elbit"],
        "AZRG.TA": ["azrieli"],
        "^GSPC": ["s&p 500", "s&p500", "sp500"],
        "^IXIC": ["nasdaq"],
        "CL=F": ["crude oil", "oil price", "wti"],
        "GC=F": ["gold price", "gold futures"],
    }

    for symbol, keywords in symbol_keywords.items():
        if any(kw in headline_lower for kw in keywords):
            symbols.append(symbol)

    return ",".join(symbols) if symbols else ""


def fetch_rss_news() -> list[SentimentRecord]:
    """Fetch and analyze news from RSS feeds."""
    records = []

    for feed_key, feed_config in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_config["url"])

            for entry in feed.entries[:10]:  # Limit to 10 per feed
                title = entry.get("title", "")
                if not title:
                    continue

                description = entry.get("summary", "")
                full_text = f"{title}. {description}" if description else title

                sentiment = analyze_sentiment(full_text)
                sector = classify_sector(full_text)
                symbols = find_related_symbols(full_text)

                record = SentimentRecord(
                    headline=title,
                    source=feed_config["source"],
                    url=entry.get("link", ""),
                    sentiment_score=sentiment,
                    sector=sector,
                    related_symbols=symbols,
                    timestamp=datetime.utcnow(),
                )
                records.append(record)

        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_key}: {e}")

    return records


def fetch_newsapi_headlines() -> list[SentimentRecord]:
    """Fetch headlines from NewsAPI (free tier: 100 requests/day)."""
    if not settings.NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set - skipping NewsAPI fetch")
        return []

    records = []
    queries = [
        "stock market",
        "Israel economy",
        "Tel Aviv stock exchange",
        "Federal Reserve interest rate",
    ]

    for query in queries:
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 5,
                    "apiKey": settings.NEWS_API_KEY,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for article in data.get("articles", []):
                title = article.get("title", "")
                if not title:
                    continue

                description = article.get("description", "")
                full_text = f"{title}. {description}" if description else title

                sentiment = analyze_sentiment(full_text)
                sector = classify_sector(full_text)
                symbols = find_related_symbols(full_text)

                record = SentimentRecord(
                    headline=title,
                    source=article.get("source", {}).get("name", "NewsAPI"),
                    url=article.get("url", ""),
                    sentiment_score=sentiment,
                    sector=sector,
                    related_symbols=symbols,
                    timestamp=datetime.utcnow(),
                )
                records.append(record)

        except Exception as e:
            logger.error(f"Error fetching NewsAPI for '{query}': {e}")

    return records


def get_sector_sentiment_summary() -> dict:
    """Get aggregated sentiment by sector from recent records."""
    db = SessionLocal()
    try:
        from sqlalchemy import func

        results = (
            db.query(
                SentimentRecord.sector,
                func.avg(SentimentRecord.sentiment_score).label("avg_sentiment"),
                func.count(SentimentRecord.id).label("article_count"),
            )
            .filter(SentimentRecord.sector.isnot(None))
            .group_by(SentimentRecord.sector)
            .all()
        )

        summary = {}
        for row in results:
            avg = round(float(row.avg_sentiment), 3)
            summary[row.sector] = {
                "avg_sentiment": avg,
                "article_count": row.article_count,
                "tone": "positive" if avg > 0.1 else "negative" if avg < -0.1 else "neutral",
            }
        return summary
    finally:
        db.close()


def save_sentiment_records(records: list[SentimentRecord]):
    """Persist sentiment records to the database."""
    if not records:
        return

    db = SessionLocal()
    try:
        db.add_all(records)
        db.commit()
        logger.info(f"Saved {len(records)} sentiment records")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving sentiment records: {e}")
    finally:
        db.close()


def run_sentiment_ingestion():
    """Run a full news sentiment ingestion cycle."""
    logger.info("Starting news sentiment ingestion...")

    records = []
    records.extend(fetch_rss_news())
    records.extend(fetch_newsapi_headlines())

    save_sentiment_records(records)
    logger.info(f"Sentiment ingestion complete: {len(records)} records")
    return records
