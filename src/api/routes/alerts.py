"""Alert management API routes."""

from fastapi import APIRouter, Query
from sqlalchemy import desc

from src.alerts.causal_alerts import get_recent_alerts, run_alert_generation
from src.models.database import Alert, SessionLocal

router = APIRouter()


@router.get("/")
async def list_alerts(
    limit: int = Query(20, ge=1, le=100),
    severity: str | None = Query(None, description="Filter: info, warning, critical"),
    unread_only: bool = Query(False),
):
    """Get recent alerts with causal explanations."""
    db = SessionLocal()
    try:
        query = db.query(Alert).order_by(desc(Alert.timestamp))

        if severity:
            query = query.filter(Alert.severity == severity)
        if unread_only:
            query = query.filter(Alert.is_read == 0)

        results = query.limit(limit).all()
        return [
            {
                "id": a.id,
                "type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "description": a.description,
                "related_symbols": a.related_symbols,
                "cause": a.cause_event,
                "timestamp": a.timestamp.isoformat(),
                "is_read": bool(a.is_read),
            }
            for a in results
        ]
    finally:
        db.close()


@router.post("/{alert_id}/read")
async def mark_alert_read(alert_id: int):
    """Mark an alert as read."""
    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return {"error": "Alert not found"}
        alert.is_read = 1
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@router.post("/refresh")
async def trigger_alert_refresh():
    """Manually trigger alert generation."""
    alerts = run_alert_generation()
    return {"status": "ok", "alerts_generated": len(alerts)}
