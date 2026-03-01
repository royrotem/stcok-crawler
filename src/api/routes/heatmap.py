"""Heatmap API route - TASE sector heatmap data."""

from fastapi import APIRouter

from src.analysis.insights import generate_sector_heatmap_data, generate_timeline_events

router = APIRouter()


@router.get("/sectors")
async def get_sector_heatmap():
    """Get TASE sector heatmap data.

    Returns sector-level performance colored by overnight Wall Street impact.
    """
    return generate_sector_heatmap_data()


@router.get("/timeline")
async def get_timeline(limit: int = 50):
    """Get a unified timeline of global/local events and market moves."""
    return generate_timeline_events(limit)
