import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
from typing import List

from core.storage.mongo import get_mongo_db
from core.analytics.export import (
    export_visitor_report_csv,
    export_peak_hours_csv,
    export_camera_health_csv,
    export_zone_stats_csv
)
from core.analytics.heatmap import HeatmapGenerator


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


class ZoneStatsItem(BaseModel):
    zone_name: str
    unique_visitors: int
    total_dwell_minutes: float
    avg_dwell_minutes: float
    visit_count: int


class ZoneStatsResponse(BaseModel):
    zones: list[ZoneStatsItem]
    total_zones: int


class ZoneTransitionItem(BaseModel):
    from_zone: str
    to_zone: str
    count: int


class ZoneTransitionsResponse(BaseModel):
    transitions: list[ZoneTransitionItem]
    total_transitions: int


class VisitorPathItem(BaseModel):
    camera_id: str
    timestamp: str
    zone: str | None


class VisitorJourneyResponse(BaseModel):
    visitor_id: str
    path: list[VisitorPathItem]
    total_cameras: int
    total_zones: int


class AnomalyItem(BaseModel):
    type: str
    severity: str
    camera_id: str | None
    zone: str | None
    timestamp: str
    description: str
    value: float | None


class AnomalyResponse(BaseModel):
    anomalies: list[AnomalyItem]
    total_count: int
    critical_count: int


class DailyTrendItem(BaseModel):
    date: str
    total_visitors: int
    avg_dwell_minutes: float
    peak_hour: str
    busiest_camera: str


class WeeklyTrendResponse(BaseModel):
    days: list[DailyTrendItem]
    week_total: int
    week_avg_dwell: float
    trend: str  # "increasing", "decreasing", "stable"


class HeatmapStatsResponse(BaseModel):
    camera_id: str
    max_density: float
    mean_density: float
    active_cells: int
    coverage_percent: float
    hotspot_count: int
    time_range: str


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


@app.get("/analytics/zone-stats", response_model=ZoneStatsResponse, tags=["analytics"])
def get_zone_stats(date_str: str = None) -> ZoneStatsResponse:
    """Get statistics per zone (visitor count, dwell time)"""
    db = get_mongo_db()
    
    # Use today if no date specified
    if date_str:
        target_date = datetime.fromisoformat(date_str).date()
    else:
        target_date = datetime.utcnow().date()
    
    start_of_day = datetime(target_date.year, target_date.month, target_date.day)
    end_of_day = start_of_day + timedelta(days=1)
    
    # Get zone activity events
    zone_events = list(db.activity_events.find({
        "start_time": {"$gte": start_of_day, "$lt": end_of_day}
    }))
    
    # Aggregate by zone
    zone_stats = {}
    for event in zone_events:
        zone = event.get('zone', 'unknown')
        visitor_id = event.get('visitor_id')
        
        if zone not in zone_stats:
            zone_stats[zone] = {
                "visitors": set(),
                "total_dwell": 0.0,
                "visit_count": 0
            }
        
        zone_stats[zone]["visitors"].add(str(visitor_id))
        zone_stats[zone]["visit_count"] += 1
        
        # Calculate dwell time
        start = event.get('start_time')
        end = event.get('end_time')
        if start and end:
            dwell = (end - start).total_seconds()
            zone_stats[zone]["total_dwell"] += dwell
    
    # Build response
    zones = []
    for zone_name, stats in zone_stats.items():
        unique_count = len(stats["visitors"])
        total_dwell_min = stats["total_dwell"] / 60.0
        avg_dwell_min = total_dwell_min / stats["visit_count"] if stats["visit_count"] > 0 else 0.0
        
        zones.append(ZoneStatsItem(
            zone_name=zone_name,
            unique_visitors=unique_count,
            total_dwell_minutes=round(total_dwell_min, 2),
            avg_dwell_minutes=round(avg_dwell_min, 2),
            visit_count=stats["visit_count"]
        ))
    
    return ZoneStatsResponse(
        zones=sorted(zones, key=lambda x: x.unique_visitors, reverse=True),
        total_zones=len(zones)
    )


@app.get("/analytics/zone-transitions", response_model=ZoneTransitionsResponse, tags=["analytics"])
def get_zone_transitions(date_str: str = None) -> ZoneTransitionsResponse:
    """Get zone transition matrix (how visitors move between zones)"""
    db = get_mongo_db()
    
    # Use today if no date specified
    if date_str:
        target_date = datetime.fromisoformat(date_str).date()
    else:
        target_date = datetime.utcnow().date()
    
    start_of_day = datetime(target_date.year, target_date.month, target_date.day)
    end_of_day = start_of_day + timedelta(days=1)
    
    # Get zone activity events sorted by visitor and time
    zone_events = list(db.activity_events.find({
        "start_time": {"$gte": start_of_day, "$lt": end_of_day}
    }).sort([("visitor_id", 1), ("start_time", 1)]))
    
    # Track transitions
    transitions = {}
    prev_zone_by_visitor = {}
    
    for event in zone_events:
        visitor_id = str(event.get('visitor_id'))
        current_zone = event.get('zone', 'unknown')
        
        if visitor_id in prev_zone_by_visitor:
            prev_zone = prev_zone_by_visitor[visitor_id]
            if prev_zone != current_zone:
                # Record transition
                key = f"{prev_zone} -> {current_zone}"
                transitions[key] = transitions.get(key, 0) + 1
        
        prev_zone_by_visitor[visitor_id] = current_zone
    
    # Build response
    transition_items = []
    for key, count in sorted(transitions.items(), key=lambda x: x[1], reverse=True):
        from_zone, to_zone = key.split(" -> ")
        transition_items.append(ZoneTransitionItem(
            from_zone=from_zone,
            to_zone=to_zone,
            count=count
        ))
    
    return ZoneTransitionsResponse(
        transitions=transition_items,
        total_transitions=sum(transitions.values())
    )


@app.get("/analytics/visitor-journey/{visitor_id}", response_model=VisitorJourneyResponse, tags=["analytics"])
def get_visitor_journey(visitor_id: str) -> VisitorJourneyResponse:
    """Get the complete journey of a visitor across cameras and zones"""
    db = get_mongo_db()
    
    # Get all visit events for this visitor (by global_id)
    visit_events = list(db.visit_events.find({
        "global_id": visitor_id
    }).sort("in_time", 1))
    
    # Get zone activities
    # First, get visitor document to find _id
    visitor_doc = db.visitors.find_one({"global_id": visitor_id})
    zone_activities = []
    if visitor_doc:
        zone_activities = list(db.activity_events.find({
            "visitor_id": visitor_doc['_id']
        }).sort("start_time", 1))
    
    # Build combined path
    path = []
    cameras_seen = set()
    zones_seen = set()
    
    # Add camera visits
    for event in visit_events:
        camera_id = event.get('camera_id')
        timestamp = event.get('in_time')
        cameras_seen.add(camera_id)
        
        # Try to match with zone activity
        matching_zone = None
        for zone_event in zone_activities:
            if abs((zone_event.get('start_time') - timestamp).total_seconds()) < 5:
                matching_zone = zone_event.get('zone')
                zones_seen.add(matching_zone)
                break
        
        path.append(VisitorPathItem(
            camera_id=camera_id,
            timestamp=timestamp.isoformat(),
            zone=matching_zone
        ))
    
    return VisitorJourneyResponse(
        visitor_id=visitor_id,
        path=path,
        total_cameras=len(cameras_seen),
        total_zones=len(zones_seen)
    )


@app.get("/analytics/anomalies", response_model=AnomalyResponse, tags=["analytics"])
def get_anomalies(hours: int = 1) -> AnomalyResponse:
    """Detect anomalies in visitor patterns"""
    db = get_mongo_db()
    now = datetime.utcnow()
    since = now - timedelta(hours=hours)
    
    anomalies = []
    
    # 1. Detect sudden crowd formation (>20 visitors in 5 min window)
    recent_visits = list(db.visit_events.find({
        "in_time": {"$gte": since}
    }))
    
    # Group by 5-minute windows
    from collections import defaultdict
    windows = defaultdict(list)
    for visit in recent_visits:
        window_key = visit['in_time'].replace(second=0, microsecond=0)
        window_key = window_key.replace(minute=(window_key.minute // 5) * 5)
        windows[window_key].append(visit)
    
    for window_time, visits in windows.items():
        if len(visits) > 20:
            anomalies.append(AnomalyItem(
                type="sudden_crowd",
                severity="🔴 Critical",
                camera_id=visits[0]['camera_id'],
                zone=None,
                timestamp=window_time.isoformat(),
                description=f"Sudden crowd detected: {len(visits)} arrivals in 5 minutes",
                value=float(len(visits))
            ))
    
    # 2. Detect camera failures (no detections in last 10 minutes)
    ten_min_ago = now - timedelta(minutes=10)
    all_cameras = db.visit_events.distinct("camera_id")
    
    for camera_id in all_cameras:
        last_detection = db.visit_events.find_one(
            {"camera_id": camera_id},
            sort=[("in_time", -1)]
        )
        
        if last_detection and last_detection['in_time'] < ten_min_ago:
            anomalies.append(AnomalyItem(
                type="camera_failure",
                severity="🔴 Critical",
                camera_id=camera_id,
                zone=None,
                timestamp=last_detection['in_time'].isoformat(),
                description=f"Camera {camera_id} inactive for {int((now - last_detection['in_time']).total_seconds()/60)} minutes",
                value=None
            ))
    
    # 3. Detect unusual dwell time (>2 hours)
    long_dwell_visits = db.visit_events.find({
        "in_time": {"$gte": since},
        "out_time": None
    })
    
    for visit in long_dwell_visits:
        dwell_hours = (now - visit['in_time']).total_seconds() / 3600
        if dwell_hours > 2:
            anomalies.append(AnomalyItem(
                type="unusual_dwell",
                severity="🟡 Warning",
                camera_id=visit['camera_id'],
                zone=None,
                timestamp=visit['in_time'].isoformat(),
                description=f"Visitor {visit.get('global_id', 'unknown')} present for {dwell_hours:.1f} hours",
                value=dwell_hours
            ))
    
    # Count critical anomalies
    critical_count = len([a for a in anomalies if "Critical" in a.severity])
    
    return AnomalyResponse(
        anomalies=sorted(anomalies, key=lambda x: x.timestamp, reverse=True),
        total_count=len(anomalies),
        critical_count=critical_count
    )


@app.get("/export/visitors.csv", tags=["export"])
def export_visitors(date_str: str = None) -> Response:
    """Export visitor report as CSV"""
    db = get_mongo_db()
    
    if date_str:
        target_date = datetime.fromisoformat(date_str).date()
    else:
        target_date = datetime.utcnow().date()
    
    start = datetime(target_date.year, target_date.month, target_date.day)
    end = start + timedelta(days=1)
    
    csv_content = export_visitor_report_csv(db, start, end)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=visitors_{target_date}.csv"
        }
    )


@app.get("/export/peak-hours.csv", tags=["export"])
def export_peak_hours(date_str: str = None) -> Response:
    """Export peak hours analysis as CSV"""
    db = get_mongo_db()
    
    if date_str:
        target_date = datetime.fromisoformat(date_str).date()
    else:
        target_date = datetime.utcnow().date()
    
    csv_content = export_peak_hours_csv(db, target_date)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=peak_hours_{target_date}.csv"
        }
    )


@app.get("/export/camera-health.csv", tags=["export"])
def export_camera_health() -> Response:
    """Export camera health status as CSV"""
    db = get_mongo_db()
    
    csv_content = export_camera_health_csv(db)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=camera_health.csv"
        }
    )


@app.get("/export/zone-stats.csv", tags=["export"])
def export_zone_stats(date_str: str = None) -> Response:
    """Export zone statistics as CSV"""
    db = get_mongo_db()
    
    if date_str:
        target_date = datetime.fromisoformat(date_str).date()
    else:
        target_date = datetime.utcnow().date()
    
    csv_content = export_zone_stats_csv(db, target_date)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=zone_stats_{target_date}.csv"
        }
    )


@app.get("/analytics/weekly-trend", response_model=WeeklyTrendResponse, tags=["analytics"])
def get_weekly_trend(weeks_back: int = 1) -> WeeklyTrendResponse:
    """Analyze visitor trends over the past week(s)"""
    db = get_mongo_db()
    
    now = datetime.utcnow()
    end_date = datetime(now.year, now.month, now.day) + timedelta(days=1)
    start_date = end_date - timedelta(days=7 * weeks_back)
    
    daily_stats = []
    
    # Iterate through each day
    current_date = start_date
    while current_date < end_date:
        next_date = current_date + timedelta(days=1)
        
        # Get visits for this day
        visits = list(db.visit_events.find({
            "in_time": {"$gte": current_date, "$lt": next_date}
        }))
        
        total_visitors = len(set(v.get('global_id') for v in visits if v.get('global_id')))
        
        # Calculate average dwell
        total_dwell = 0.0
        dwell_count = 0
        for visit in visits:
            if visit.get('out_time'):
                dwell = (visit['out_time'] - visit['in_time']).total_seconds() / 60
                total_dwell += dwell
                dwell_count += 1
        
        avg_dwell = total_dwell / dwell_count if dwell_count > 0 else 0.0
        
        # Find peak hour
        hourly_counts = {}
        for visit in visits:
            hour = visit['in_time'].hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        peak_hour = max(hourly_counts.items(), key=lambda x: x[1])[0] if hourly_counts else 0
        
        # Find busiest camera
        camera_counts = {}
        for visit in visits:
            cam = visit.get('camera_id', 'unknown')
            camera_counts[cam] = camera_counts.get(cam, 0) + 1
        
        busiest_camera = max(camera_counts.items(), key=lambda x: x[1])[0] if camera_counts else 'none'
        
        daily_stats.append(DailyTrendItem(
            date=current_date.date().isoformat(),
            total_visitors=total_visitors,
            avg_dwell_minutes=round(avg_dwell, 2),
            peak_hour=f"{peak_hour:02d}:00",
            busiest_camera=busiest_camera
        ))
        
        current_date = next_date
    
    # Calculate weekly totals and trend
    week_total = sum(d.total_visitors for d in daily_stats)
    week_avg_dwell = sum(d.avg_dwell_minutes for d in daily_stats) / len(daily_stats) if daily_stats else 0.0
    
    # Determine trend (compare first half vs second half)
    if len(daily_stats) >= 4:
        mid = len(daily_stats) // 2
        first_half_avg = sum(d.total_visitors for d in daily_stats[:mid]) / mid
        second_half_avg = sum(d.total_visitors for d in daily_stats[mid:]) / (len(daily_stats) - mid)
        
        if second_half_avg > first_half_avg * 1.1:
            trend = "📈 Increasing"
        elif second_half_avg < first_half_avg * 0.9:
            trend = "📉 Decreasing"
        else:
            trend = "➡️ Stable"
    else:
        trend = "➡️ Stable"
    
    return WeeklyTrendResponse(
        days=daily_stats,
        week_total=week_total,
        week_avg_dwell=round(week_avg_dwell, 2),
        trend=trend
    )


@app.get("/analytics/heatmap/{camera_id}", response_model=HeatmapStatsResponse, tags=["analytics"])
def get_heatmap_stats(camera_id: str, hours: int = 1) -> HeatmapStatsResponse:
    """Get person density heatmap statistics for a camera"""
    db = get_mongo_db()
    
    now = datetime.utcnow()
    start_time = now - timedelta(hours=hours)
    
    # Create heatmap from database
    heatmap = HeatmapGenerator.create_from_db(
        db, camera_id, start_time, now, width=1920, height=1080
    )
    
    stats = heatmap.get_statistics()
    
    return HeatmapStatsResponse(
        camera_id=camera_id,
        max_density=stats['max_density'],
        mean_density=stats['mean_density'],
        active_cells=stats['active_cells'],
        coverage_percent=stats['coverage_percent'],
        hotspot_count=stats['hotspot_count'],
        time_range=f"Last {hours} hour(s)"
    )


@app.get("/analytics/heatmap/{camera_id}/image.png", tags=["analytics"])
def get_heatmap_image(camera_id: str, hours: int = 1) -> Response:
    """Generate heatmap visualization image"""
    db = get_mongo_db()
    
    now = datetime.utcnow()
    start_time = now - timedelta(hours=hours)
    
    # Create heatmap from database
    heatmap = HeatmapGenerator.create_from_db(
        db, camera_id, start_time, now, width=1920, height=1080
    )
    
    # Generate image
    import cv2
    heatmap_img = heatmap.get_heatmap_image(colormap=cv2.COLORMAP_JET)
    
    # Convert to PNG
    success, buffer = cv2.imencode('.png', cv2.cvtColor(heatmap_img, cv2.COLOR_RGB2BGR))
    
    if not success:
        return Response(
            content="Failed to generate heatmap image",
            status_code=500
        )
    
    return Response(
        content=buffer.tobytes(),
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename=heatmap_{camera_id}_{hours}h.png"
        }
    )

