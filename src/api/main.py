import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

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
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)
    total_today = db.query(VisitEvent).filter(VisitEvent.in_time >= start).count()
    active = db.query(VisitEvent).filter(VisitEvent.out_time.is_(None)).count()
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

@app.post("/reset-daily")
def reset_daily(db: Session = Depends(get_session)) -> dict:
    # Archive: mark open events as closed at reset time
    now = datetime.utcnow()
    open_visits = db.query(VisitEvent).filter(VisitEvent.out_time.is_(None)).all()
    for v in open_visits:
        v.out_time = now
    open_acts = db.query(ActivityEvent).filter(ActivityEvent.end_time.is_(None)).all()
    for a in open_acts:
        a.end_time = now
    db.commit()
    return {"status": "reset_ok"}


