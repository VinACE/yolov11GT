"""
Export analytics data to CSV/Excel formats
"""
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, List


def export_visitor_report_csv(db, start_date: datetime, end_date: datetime) -> str:
    """Export visitor statistics to CSV format"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Global ID",
        "First Seen",
        "Last Seen",
        "Total Dwell (minutes)",
        "Cameras Visited",
        "Visit Count"
    ])
    
    # Get visitors in date range
    visitors = list(db.visitors.find({
        "first_seen_at": {"$gte": start_date, "$lt": end_date}
    }))
    
    for visitor in visitors:
        global_id = visitor.get('global_id', 'unknown')
        first_seen = visitor.get('first_seen_at', '').isoformat() if visitor.get('first_seen_at') else ''
        last_seen = visitor.get('last_seen_at', '').isoformat() if visitor.get('last_seen_at') else ''
        
        # Calculate dwell time
        if visitor.get('first_seen_at') and visitor.get('last_seen_at'):
            dwell_seconds = (visitor['last_seen_at'] - visitor['first_seen_at']).total_seconds()
            dwell_minutes = round(dwell_seconds / 60, 2)
        else:
            dwell_minutes = 0
        
        # Get cameras and visit count
        visits = list(db.visit_events.find({"visitor_id": visitor['_id']}))
        cameras = set(v.get('camera_id') for v in visits)
        
        writer.writerow([
            global_id,
            first_seen,
            last_seen,
            dwell_minutes,
            ", ".join(sorted(cameras)),
            len(visits)
        ])
    
    return output.getvalue()


def export_peak_hours_csv(db, date: datetime) -> str:
    """Export peak hours analysis to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Hour",
        "Visitor Count",
        "Avg Dwell Time (minutes)",
        "Unique Visitors"
    ])
    
    start_of_day = datetime(date.year, date.month, date.day)
    end_of_day = start_of_day + timedelta(days=1)
    
    # Get all visits for the day
    visits = list(db.visit_events.find({
        "in_time": {"$gte": start_of_day, "$lt": end_of_day}
    }))
    
    # Aggregate by hour
    hourly_stats = {}
    for hour in range(24):
        hourly_stats[hour] = {
            "count": 0,
            "total_dwell": 0.0,
            "visitors": set()
        }
    
    for visit in visits:
        entry_hour = visit['in_time'].hour
        hourly_stats[entry_hour]["count"] += 1
        hourly_stats[entry_hour]["visitors"].add(visit.get('global_id', ''))
        
        # Calculate dwell time if visit closed
        if visit.get('out_time'):
            dwell = (visit['out_time'] - visit['in_time']).total_seconds() / 60
            hourly_stats[entry_hour]["total_dwell"] += dwell
    
    # Write data
    for hour in range(24):
        stats = hourly_stats[hour]
        count = stats["count"]
        avg_dwell = stats["total_dwell"] / count if count > 0 else 0.0
        unique = len(stats["visitors"])
        
        writer.writerow([
            f"{hour:02d}:00",
            count,
            round(avg_dwell, 2),
            unique
        ])
    
    return output.getvalue()


def export_camera_health_csv(db) -> str:
    """Export camera health status to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Camera ID",
        "Status",
        "Last Detection",
        "Detections (Last 5 min)",
        "Total Events Today"
    ])
    
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    five_min_ago = now - timedelta(minutes=5)
    
    # Get all unique cameras
    all_cameras = db.visit_events.distinct("camera_id")
    
    for camera_id in sorted(all_cameras):
        # Last detection
        last_event = db.visit_events.find_one(
            {"camera_id": camera_id},
            sort=[("in_time", -1)]
        )
        
        if last_event:
            last_time = last_event['in_time']
            time_ago_seconds = (now - last_time).total_seconds()
            
            if time_ago_seconds < 120:
                status = "Active"
            elif time_ago_seconds < 300:
                status = "Slow"
            else:
                status = "Inactive"
            
            last_detection = last_time.isoformat()
        else:
            status = "No Data"
            last_detection = "Never"
        
        # Recent detections
        recent_count = db.visit_events.count_documents({
            "camera_id": camera_id,
            "in_time": {"$gte": five_min_ago}
        })
        
        # Today's total
        today_count = db.visit_events.count_documents({
            "camera_id": camera_id,
            "in_time": {"$gte": today_start}
        })
        
        writer.writerow([
            camera_id,
            status,
            last_detection,
            recent_count,
            today_count
        ])
    
    return output.getvalue()


def export_zone_stats_csv(db, date: datetime) -> str:
    """Export zone statistics to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Zone Name",
        "Unique Visitors",
        "Total Visits",
        "Total Dwell Time (minutes)",
        "Avg Dwell Time (minutes)"
    ])
    
    start_of_day = datetime(date.year, date.month, date.day)
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
            dwell = (end - start).total_seconds() / 60
            zone_stats[zone]["total_dwell"] += dwell
    
    # Write data
    for zone_name in sorted(zone_stats.keys()):
        stats = zone_stats[zone_name]
        unique_count = len(stats["visitors"])
        total_dwell = round(stats["total_dwell"], 2)
        avg_dwell = round(total_dwell / stats["visit_count"], 2) if stats["visit_count"] > 0 else 0.0
        
        writer.writerow([
            zone_name,
            unique_count,
            stats["visit_count"],
            total_dwell,
            avg_dwell
        ])
    
    return output.getvalue()

