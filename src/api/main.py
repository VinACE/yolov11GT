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


