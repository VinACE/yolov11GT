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


class PeakHourItem(BaseModel):
    hour: str
    visitor_count: int
    avg_dwell_minutes: float


class PeakHoursResponse(BaseModel):
    peak_hours: list[PeakHourItem]
    busiest_hour: str
    quietest_hour: str


class CameraHealthItem(BaseModel):
    camera_id: str
    status: str
    last_detection: str
    detections_last_5min: int
    reid_match_rate: float


class CameraHealthResponse(BaseModel):
    cameras: list[CameraHealthItem]
    overall_status: str


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


@app.get("/analytics/peak-hours", response_model=PeakHoursResponse, tags=["analytics"])
def get_peak_hours(date_str: str = None) -> PeakHoursResponse:
    """Analyze peak hours by visitor arrivals and dwell time"""
    db = get_mongo_db()
    
    # Use today if no date specified
    if date_str:
        target_date = datetime.fromisoformat(date_str).date()
    else:
        target_date = datetime.utcnow().date()
    
    start_of_day = datetime(target_date.year, target_date.month, target_date.day)
    end_of_day = start_of_day + timedelta(days=1)
    
    # Get all visits for the day
    visits = list(db.visit_events.find({
        "in_time": {"$gte": start_of_day, "$lt": end_of_day}
    }))
    
    # Aggregate by hour
    hourly_stats = {}
    for hour in range(24):
        hourly_stats[hour] = {"arrivals": 0, "total_dwell": 0.0}
    
    for visit in visits:
        entry_hour = visit['in_time'].hour
        hourly_stats[entry_hour]["arrivals"] += 1
        
        # Calculate dwell time if visit closed
        if visit.get('out_time'):
            dwell = (visit['out_time'] - visit['in_time']).total_seconds()
            hourly_stats[entry_hour]["total_dwell"] += dwell
    
    # Build response
    peak_data = []
    max_count = 0
    min_count = float('inf')
    busiest_hour = "00:00"
    quietest_hour = "00:00"
    
    for hour in range(24):
        stats = hourly_stats[hour]
        arrivals = stats["arrivals"]
        avg_dwell = stats["total_dwell"] / arrivals / 60.0 if arrivals > 0 else 0.0
        
        peak_data.append(PeakHourItem(
            hour=f"{hour:02d}:00",
            visitor_count=arrivals,
            avg_dwell_minutes=round(avg_dwell, 2)
        ))
        
        if arrivals > max_count:
            max_count = arrivals
            busiest_hour = f"{hour:02d}:00"
        
        if arrivals < min_count and arrivals > 0:  # Ignore hours with 0
            min_count = arrivals
            quietest_hour = f"{hour:02d}:00"
    
    return PeakHoursResponse(
        peak_hours=peak_data,
        busiest_hour=busiest_hour,
        quietest_hour=quietest_hour
    )


@app.get("/system/camera-health", response_model=CameraHealthResponse, tags=["system"])
def get_camera_health() -> CameraHealthResponse:
    """Monitor camera health and ReID performance"""
    db = get_mongo_db()
    
    # Get all unique cameras
    all_cameras = db.visit_events.distinct("camera_id")
    
    camera_health = []
    all_healthy = True
    now = datetime.utcnow()
    five_min_ago = now - timedelta(minutes=5)
    
    for camera_id in sorted(all_cameras):
        # Recent detections
        recent_count = db.visit_events.count_documents({
            "camera_id": camera_id,
            "in_time": {"$gte": five_min_ago}
        })
        
        # Last detection time
        last_event = db.visit_events.find_one(
            {"camera_id": camera_id},
            sort=[("in_time", -1)]
        )
        
        last_detection = "Never"
        status = "🟢 Active"
        if last_event:
            last_time = last_event['in_time']
            time_ago = (now - last_time).total_seconds()
            if time_ago < 60:
                last_detection = f"{int(time_ago)}s ago"
            elif time_ago < 3600:
                last_detection = f"{int(time_ago/60)}m ago"
            else:
                last_detection = f"{int(time_ago/3600)}h ago"
            
            if time_ago > 300:  # 5 minutes
                status = "🔴 Inactive"
                all_healthy = False
            elif time_ago > 120:  # 2 minutes
                status = "🟡 Slow"
        else:
            status = "⚫ No Data"
            all_healthy = False
        
        # Calculate ReID match rate for this camera
        # Get assignments from reid_assignment_log if available, or estimate from visit events
        # For now, use a simple heuristic
        reid_match_rate = 0.85  # Placeholder - could read from logs
        
        camera_health.append(CameraHealthItem(
            camera_id=camera_id,
            status=status,
            last_detection=last_detection,
            detections_last_5min=recent_count,
            reid_match_rate=round(reid_match_rate, 2)
        ))
    
    overall = "🟢 All Systems Operational" if all_healthy else "🔴 Issues Detected"
    
    return CameraHealthResponse(
        cameras=camera_health,
        overall_status=overall
    )

