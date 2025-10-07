import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
from typing import List

from core.storage.mongo import get_mongo_db


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


class PresenceHourItem(BaseModel):
    hour_start: datetime
    arrivals: int
    presence_minutes: float
    unique_visitors: int


class PresenceHourlyResponse(BaseModel):
    date_utc: str
    buckets: list[PresenceHourItem]


class RecentVisitorsResponse(BaseModel):
    visitors: list[str]


class EventsResponse(BaseModel):
    events: list[dict]


@app.on_event("startup")
def on_startup() -> None:
    _ = get_mongo_db()


@app.get("/health", response_model=HealthResponse, tags=["system"], description="Liveness probe")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/stats", response_model=StatsResponse, tags=["analytics"], description="Active visitors and unique today")
def stats() -> StatsResponse:
    db = get_mongo_db()
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)
    
    gids_events = set(g for g in db.visit_events.distinct(
        "global_id",
        {"in_time": {"$gte": start}, "global_id": {"$exists": True}}
    ) if g is not None)
    gids_seen = set(v.get("global_id") for v in db.visitors.find(
        {"last_seen_at": {"$gte": start}}, {"global_id": 1}
    ))
    gids_seen.discard(None)
    total_today = len(gids_events.union(gids_seen))

    timeout_seconds = int(os.environ.get("VISITOR_TIMEOUT_SECONDS", "30"))
    cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)
    recent_visitors = set(v["_id"] for v in db.visitors.find({"last_seen_at": {"$gte": cutoff}}, {"_id": 1}))
    active = db.visit_events.count_documents({"out_time": None, "visitor_id": {"$in": list(recent_visitors)}})
    return StatsResponse(active_visitors=active, total_today=total_today)


@app.get("/time-spent", response_model=TimeSpentResponse, tags=["analytics"])
def get_time_spent() -> TimeSpentResponse:
    db = get_mongo_db()
    visitors = list(db.visitors.find())
    result: List[VisitorTimeInfo] = []
    
    for visitor in visitors:
        entry_time = visitor.get("first_seen_at")
        exit_time = visitor.get("last_seen_at")
        
        if entry_time and exit_time:
            time_diff = exit_time - entry_time
            time_spent_seconds = time_diff.total_seconds()
            
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
            global_id=visitor.get("global_id"),
            entry_time=entry_time,
            exit_time=exit_time if entry_time != exit_time else None,
            time_spent_seconds=time_spent_seconds,
            time_spent_formatted=formatted
        ))
    
    return TimeSpentResponse(visitors=result)


@app.get("/dwell-stats", response_model=DwellStatsResponse, tags=["analytics"])
def dwell_stats() -> DwellStatsResponse:
    db = get_mongo_db()
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)

    visitor_ids = set(doc["visitor_id"] for doc in db.visit_events.find({"in_time": {"$gte": start}}, {"visitor_id": 1}))
    visitors = list(db.visitors.find({"_id": {"$in": list(visitor_ids)}}))

    items: list[DwellItem] = []
    dwell_vals: list[float] = []
    for v in visitors:
        dwell_sec = max(0.0, (v.get("last_seen_at") - v.get("first_seen_at")).total_seconds())
        dwell_vals.append(dwell_sec)
        items.append(
            DwellItem(
                global_id=v.get("global_id"),
                first_seen_at=v.get("first_seen_at"),
                last_seen_at=v.get("last_seen_at"),
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


@app.get("/presence-hourly", response_model=PresenceHourlyResponse, tags=["analytics"])
def presence_hourly() -> PresenceHourlyResponse:
    db = get_mongo_db()
    now = datetime.utcnow()
    today = now.date()
    day_start = datetime(today.year, today.month, today.day)
    day_end = day_start + timedelta(days=1)

    visits = list(db.visit_events.find({
        "in_time": {"$lt": day_end},
        "$or": [{"out_time": None}, {"out_time": {"$gt": day_start}}]
    }))

    buckets: list[PresenceHourItem] = []
    for h in range(24):
        h_start = day_start + timedelta(hours=h)
        h_end = h_start + timedelta(hours=1)
        arrivals = 0
        presence_seconds = 0.0
        unique_set: set[str] = set()

        for visit in visits:
            v_start = max(visit["in_time"], day_start)
            v_end = visit.get("out_time") or now
            if v_end <= h_start or v_start >= h_end:
                continue

            overlap_start = max(v_start, h_start)
            overlap_end = min(v_end, h_end)
            overlap = (overlap_end - overlap_start).total_seconds()
            if overlap > 0:
                presence_seconds += overlap
                gid = visit.get("global_id")
                if gid:
                    unique_set.add(gid)

            if h_start <= visit["in_time"] < h_end:
                arrivals += 1

        buckets.append(
            PresenceHourItem(
                hour_start=h_start,
                arrivals=arrivals,
                presence_minutes=round(presence_seconds / 60.0, 2),
                unique_visitors=len(unique_set),
            )
        )

    return PresenceHourlyResponse(
        date_utc=str(today),
        buckets=buckets,
    )

@app.post("/reset-daily", tags=["maintenance"])
def reset_daily() -> dict:
    db = get_mongo_db()
    now = datetime.utcnow()

    db.visit_events.update_many({"out_time": None}, {"$set": {"out_time": now}})
    db.activity_events.update_many({"end_time": None}, {"$set": {"end_time": now}})

    today = now.date()
    start_of_day = datetime(today.year, today.month, today.day)

    db.activity_events.delete_many({"start_time": {"$gte": start_of_day}})
    db.visit_events.delete_many({"in_time": {"$gte": start_of_day}})

    return {"status": "reset_ok", "deleted_today": True}


@app.get("/debug/recent-visitors", response_model=RecentVisitorsResponse, tags=["debug"])
def recent_visitors(limit: int = 20) -> RecentVisitorsResponse:
    db = get_mongo_db()
    cur = db.visitors.find({}, {"global_id": 1}).sort("last_seen_at", -1).limit(int(limit))
    return RecentVisitorsResponse(visitors=[doc.get("global_id") for doc in cur])


@app.get("/debug/events", response_model=EventsResponse, tags=["debug"])
def recent_events(limit: int = 50) -> EventsResponse:
    db = get_mongo_db()
    cur = db.visit_events.find({}).sort("in_time", -1).limit(int(limit))
    events = []
    for e in cur:
        e["_id"] = str(e["_id"])
        if "visitor_id" in e:
            e["visitor_id"] = str(e["visitor_id"])
        events.append(e)
    return EventsResponse(events=events)


@app.post("/debug/reload-index", tags=["debug"])
def reload_index() -> dict:
    return {"status": "ok", "message": "No persisted index; online-only."}

