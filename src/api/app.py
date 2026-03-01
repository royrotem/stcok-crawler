"""FastAPI application setup with scheduler and routes."""

from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from loguru import logger

from config import settings
from src.models.database import init_db
from src.ingestion.market_data import run_full_market_ingestion
from src.ingestion.macro_data import run_macro_ingestion
from src.ingestion.news_sentiment import run_sentiment_ingestion
from src.alerts.causal_alerts import run_alert_generation

scheduler = BackgroundScheduler()


def setup_scheduler():
    """Configure periodic data ingestion jobs."""
    scheduler.add_job(
        run_full_market_ingestion,
        "interval",
        seconds=settings.MARKET_DATA_INTERVAL,
        id="market_data",
        name="Market Data Ingestion",
        max_instances=1,
    )
    scheduler.add_job(
        run_macro_ingestion,
        "interval",
        seconds=settings.MACRO_DATA_INTERVAL,
        id="macro_data",
        name="Macro Data Ingestion",
        max_instances=1,
    )
    scheduler.add_job(
        run_sentiment_ingestion,
        "interval",
        seconds=settings.NEWS_INTERVAL,
        id="sentiment",
        name="News Sentiment Ingestion",
        max_instances=1,
    )
    scheduler.add_job(
        run_alert_generation,
        "interval",
        seconds=settings.CORRELATION_INTERVAL,
        id="alerts",
        name="Alert Generation",
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started with periodic ingestion jobs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB and start scheduler on startup."""
    logger.info("Starting Market Intelligence System...")
    init_db()
    setup_scheduler()

    # Run initial data fetch
    logger.info("Running initial data ingestion...")
    try:
        run_full_market_ingestion()
    except Exception as e:
        logger.warning(f"Initial market ingestion failed (may be offline): {e}")
    try:
        run_macro_ingestion()
    except Exception as e:
        logger.warning(f"Initial macro ingestion failed: {e}")
    try:
        run_sentiment_ingestion()
    except Exception as e:
        logger.warning(f"Initial sentiment ingestion failed: {e}")

    logger.info("System ready.")
    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("System shutdown complete.")


app = FastAPI(
    title="TASE Market Intelligence",
    description="Real-time market intelligence system for Tel Aviv Stock Exchange "
                "with global-to-local transmission analysis",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="src/api/templates")

# Register routes
from src.api.routes.market import router as market_router
from src.api.routes.analysis import router as analysis_router
from src.api.routes.heatmap import router as heatmap_router
from src.api.routes.alerts import router as alerts_router

app.include_router(market_router, prefix="/api/market", tags=["Market Data"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(heatmap_router, prefix="/api/heatmap", tags=["Heatmap"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["Alerts"])


@app.get("/")
async def dashboard(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/health")
async def health_check():
    """System health check."""
    return {
        "status": "ok",
        "scheduler_running": scheduler.running,
        "jobs": [
            {"id": job.id, "name": job.name, "next_run": str(job.next_run_time)}
            for job in scheduler.get_jobs()
        ],
    }
