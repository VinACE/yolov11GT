import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
from sqlalchemy import func

from core.storage.db import get_db, init_db
from core.storage.models import Visitor, VisitEvent, ActivityEvent


app = FastAPI(title="Retail Analytics API", version="0.1.0")


class HealthResponse(BaseModel):
    status: str


class StatsResponse(BaseModel):
    active_visitors: int
    total_today: int

class VisitorTimeInfo(BaseModel):
    global_id: str
    entry_time: datetime
    exit_time: datetime | None
    time_spent_seconds: float | None
    time_spent_formatted: str

class TimeSpentResponse(BaseModel):
    visitors: list[VisitorTimeInfo]


class DwellItem(BaseModel):
    global_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    dwell_seconds: float


class DwellStatsResponse(BaseModel):
    total_visitors: int
    avg_dwell_seconds: float
    p50_dwell_seconds: float
    p95_dwell_seconds: float
    visitors: list[DwellItem]


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def get_session():
    with get_db() as session:
        yield session

@app.get("/stats", response_model=StatsResponse)
def stats(db: Session = Depends(get_session)) -> StatsResponse:
    """Return counts with proper active visitor semantics.

    A visitor is considered active if their most recent VisitEvent has no out_time
    and their corresponding Visitor.last_seen_at is within a timeout window.
    Timeout defaults to 30 seconds and can be overridden via VISITOR_TIMEOUT_SECONDS.
    """
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)
    total_today = db.query(VisitEvent).filter(VisitEvent.in_time >= start).count()

    timeout_seconds = int(os.environ.get("VISITOR_TIMEOUT_SECONDS", "30"))
    cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)

    # Active = open visit AND seen recently
    active = (
        db.query(func.count(func.distinct(Visitor.id)))
        .select_from(VisitEvent)
        .join(Visitor, VisitEvent.visitor_id == Visitor.id)
        .filter(VisitEvent.out_time.is_(None))
        .filter(Visitor.last_seen_at >= cutoff)
        .scalar()
    ) or 0
    return StatsResponse(active_visitors=active, total_today=total_today)


@app.get("/time-spent", response_model=TimeSpentResponse)
def get_time_spent(db: Session = Depends(get_session)) -> TimeSpentResponse:
    """Get time spent in premises for all visitors"""
    visitors = db.query(Visitor).all()
    result = []
    
    for visitor in visitors:
        entry_time = visitor.first_seen_at
        exit_time = visitor.last_seen_at
        
        # Calculate time spent
        if entry_time and exit_time:
            time_diff = exit_time - entry_time
            time_spent_seconds = time_diff.total_seconds()
            
            # Format as human-readable
            hours = int(time_spent_seconds // 3600)
            minutes = int((time_spent_seconds % 3600) // 60)
            seconds = int(time_spent_seconds % 60)
            
            if hours > 0:
                formatted = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                formatted = f"{minutes}m {seconds}s"
            else:
                formatted = f"{seconds}s"
        else:
            time_spent_seconds = None
            formatted = "Still in premises"
        
        result.append(VisitorTimeInfo(
            global_id=visitor.global_id,
            entry_time=entry_time,
            exit_time=exit_time if entry_time != exit_time else None,
            time_spent_seconds=time_spent_seconds,
            time_spent_formatted=formatted
        ))
    
    return TimeSpentResponse(visitors=result)


@app.get("/dwell-stats", response_model=DwellStatsResponse)
def dwell_stats(db: Session = Depends(get_session)) -> DwellStatsResponse:
    """Dwell summary for visitors seen today, based on ReID global IDs."""
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)

    # Pull visitors who have at least one visit today
    visitors = (
        db.query(Visitor)
        .join(VisitEvent, VisitEvent.visitor_id == Visitor.id)
        .filter(VisitEvent.in_time >= start)
        .distinct()
        .all()
    )

    items: list[DwellItem] = []
    dwell_vals: list[float] = []
    for v in visitors:
        dwell_sec = max(0.0, (v.last_seen_at - v.first_seen_at).total_seconds())
        dwell_vals.append(dwell_sec)
        items.append(
            DwellItem(
                global_id=v.global_id,
                first_seen_at=v.first_seen_at,
                last_seen_at=v.last_seen_at,
                dwell_seconds=dwell_sec,
            )
        )

    if dwell_vals:
        dwell_sorted = sorted(dwell_vals)
        n = len(dwell_sorted)
        p50 = dwell_sorted[int(0.5 * (n - 1))]
        p95 = dwell_sorted[int(0.95 * (n - 1))]
        avg = sum(dwell_sorted) / n
    else:
        avg = p50 = p95 = 0.0

    return DwellStatsResponse(
        total_visitors=len(items),
        avg_dwell_seconds=avg,
        p50_dwell_seconds=p50,
        p95_dwell_seconds=p95,
        visitors=items,
    )

@app.post("/reset-daily")
def reset_daily(db: Session = Depends(get_session)) -> dict:
    # Archive: close open events, then delete today's rows to fully reset stats
    now = datetime.utcnow()

    # Close open visits/activities
    open_visits = db.query(VisitEvent).filter(VisitEvent.out_time.is_(None)).all()
    for v in open_visits:
        v.out_time = now
    open_acts = db.query(ActivityEvent).filter(ActivityEvent.end_time.is_(None)).all()
    for a in open_acts:
        a.end_time = now

    # Compute start of "today" in UTC (keep consistent with stats endpoints)
    today = now.date()
    start_of_day = datetime(today.year, today.month, today.day)

    # Delete today's visit/activity rows
    db.query(ActivityEvent).filter(ActivityEvent.start_time >= start_of_day).delete(synchronize_session=False)
    db.query(VisitEvent).filter(VisitEvent.in_time >= start_of_day).delete(synchronize_session=False)

    db.commit()
    return {"status": "reset_ok", "deleted_today": True}


