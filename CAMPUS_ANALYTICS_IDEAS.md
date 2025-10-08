# Campus Analytics & Anomaly Detection Ideas 🎓

## Current Capabilities ✅
- Multi-camera person tracking with ReID
- Visitor counting and dwell time
- Hourly presence statistics
- Cross-camera handoff

---

## 1. 📊 Enhanced Presence Monitoring

### A. Occupancy Heatmaps
**Purpose:** Visualize high-traffic areas over time

**Implementation:**
```python
# Track position density
occupancy_grid = {}  # (camera_id, grid_x, grid_y) -> count

def update_occupancy(camera_id, bbox, timestamp):
    # Divide frame into 10x10 grid
    grid_x = int((bbox[0] + bbox[2]) / 2 / frame_width * 10)
    grid_y = int((bbox[1] + bbox[3]) / 2 / frame_height * 10)
    key = (camera_id, grid_x, grid_y, timestamp.hour)
    occupancy_grid[key] = occupancy_grid.get(key, 0) + 1
```

**MongoDB Collection:**
```javascript
{
  camera_id: "cam1",
  grid_x: 5,
  grid_y: 7,
  hour: 14,
  date: "2025-10-07",
  count: 127
}
```

**Use Cases:**
- Identify crowded zones
- Optimize facility layout
- Plan cleaning/maintenance schedules

---

### B. Real-Time Capacity Monitoring
**Purpose:** Alert when areas exceed capacity limits

**Features:**
- Zone-based occupancy (entrance, library, cafeteria, etc.)
- Configurable capacity limits per zone
- Real-time alerts when threshold exceeded
- Historical capacity utilization

**MongoDB Collection:**
```javascript
capacity_events: {
  zone: "library",
  timestamp: ISODate,
  current_count: 45,
  capacity_limit: 50,
  utilization_pct: 90.0,
  alert_triggered: false
}
```

---

### C. Temporal Patterns
**Purpose:** Understand campus usage patterns

**Metrics to Track:**
- Peak hours (busiest times)
- Low-traffic periods (maintenance windows)
- Day-of-week patterns
- Seasonal trends
- Event detection (sudden crowd surges)

**Analytics:**
```python
# Detect anomalous crowd patterns
def detect_anomaly(current_count, historical_avg, std_dev):
    z_score = (current_count - historical_avg) / std_dev
    if abs(z_score) > 3:  # 3 sigma rule
        return "ANOMALY"
    return "NORMAL"
```

---

## 2. 🔍 Anomaly Detection & Security

### A. Loitering Detection
**Purpose:** Identify people staying too long in restricted areas

**Implementation:**
```python
# Track per-zone dwell time
loitering_threshold = {
    "entrance": 300,      # 5 minutes
    "corridor": 600,      # 10 minutes
    "parking": 1800,      # 30 minutes
}

def check_loitering(visitor_id, zone, dwell_seconds):
    threshold = loitering_threshold.get(zone, 900)
    if dwell_seconds > threshold:
        return {"alert": "LOITERING", "visitor_id": visitor_id, 
                "zone": zone, "duration": dwell_seconds}
```

**MongoDB Collection:**
```javascript
security_alerts: {
  alert_type: "LOITERING",
  visitor_id: ObjectId,
  global_id: "G1234_cam1_5",
  zone: "parking",
  duration_seconds: 2100,
  timestamp: ISODate,
  camera_id: "cam1",
  bbox_snapshot: [x1, y1, x2, y2],
  resolved: false
}
```

---

### B. Restricted Area Access
**Purpose:** Detect unauthorized entry into restricted zones

**Features:**
- Define restricted zones per camera
- Time-based restrictions (e.g., after hours)
- Whitelist/blacklist global IDs
- Immediate alerts for violations

**Implementation:**
```python
restricted_zones = {
    "cam1": [
        {"name": "server_room", "polygon": [[x1,y1], [x2,y2], ...]},
        {"name": "admin_office", "polygon": [[...]], "allowed_hours": (9, 17)}
    ]
}

def check_restricted_access(global_id, camera_id, bbox, hour):
    for zone in restricted_zones.get(camera_id, []):
        if point_in_polygon(bbox_center, zone['polygon']):
            if 'allowed_hours' in zone:
                if not (zone['allowed_hours'][0] <= hour < zone['allowed_hours'][1]):
                    return {"alert": "RESTRICTED_ACCESS", "zone": zone['name']}
```

---

### C. Tailgating Detection
**Purpose:** Detect when multiple people enter through a single-person checkpoint

**Implementation:**
```python
# At entrance/exit gates
def detect_tailgating(entrance_zone, time_window=2):
    # If 2+ people detected within 2 seconds in entrance zone
    entries = get_entries_in_window(entrance_zone, time_window)
    if len(entries) > 1:
        return {"alert": "TAILGATING", "count": len(entries), 
                "global_ids": [e['global_id'] for e in entries]}
```

---

### D. Unusual Movement Patterns
**Purpose:** Detect suspicious behavior

**Patterns to Detect:**
- **Back-and-forth**: Crossing same area multiple times
- **Zone hopping**: Rapid movement between zones
- **Counter-flow**: Moving against typical traffic pattern
- **Sudden direction changes**: Erratic movement

**MongoDB Collection:**
```javascript
movement_patterns: {
  visitor_id: ObjectId,
  pattern_type: "BACK_AND_FORTH",
  zones_visited: ["entrance", "corridor", "entrance", "corridor"],
  visit_count: 4,
  time_span_seconds: 120,
  anomaly_score: 0.85
}
```

---

## 3. 💰 Monetary Leakage Detection

### A. Unaccounted Exit Detection
**Purpose:** Identify people leaving without proper checkout

**Scenario:** Campus with entry/exit gates, shops, or controlled areas

**Implementation:**
```python
# Track entry/exit balance
def check_exit_balance():
    # People who entered (detected at entrance) but not at exit
    entered = db.visit_events.distinct("visitor_id", {
        "camera_id": "entrance_cam",
        "in_time": {"$gte": today}
    })
    
    exited = db.visit_events.distinct("visitor_id", {
        "camera_id": "exit_cam", 
        "in_time": {"$gte": today}
    })
    
    unaccounted = set(entered) - set(exited)
    return unaccounted  # People still inside or left via unauthorized route
```

**Alert:**
```javascript
leakage_alerts: {
  alert_type: "UNACCOUNTED_EXIT",
  visitor_id: ObjectId,
  global_id: "G1234_entrance_1",
  entry_time: ISODate,
  last_seen_camera: "cam2",
  last_seen_time: ISODate,
  expected_exit: true,
  actual_exit: false,
  potential_revenue_loss: 50.00  // If applicable
}
```

---

### B. Dwell Time vs Transaction Correlation
**Purpose:** Detect shoplifting or service bypassing

**Use Case:** Campus bookstore, cafeteria

**Implementation:**
```python
# Correlate dwell time with transaction data (if POS integration available)
def analyze_dwell_vs_transaction(visitor_id):
    dwell_time = get_dwell_time(visitor_id, zone="bookstore")
    transaction = get_transaction(visitor_id)  # From POS system
    
    if dwell_time > 180 and transaction is None:  # 3+ min, no purchase
        return {"alert": "POTENTIAL_THEFT", "dwell_seconds": dwell_time}
    
    if dwell_time > 600 and transaction['amount'] < 10:  # 10+ min, low value
        return {"alert": "SUSPICIOUS_LOW_VALUE"}
```

---

### C. High-Value Area Monitoring
**Purpose:** Track who accesses valuable items/areas

**Implementation:**
```python
high_value_zones = {
    "electronics_section": {"min_dwell_alert": 180, "frequent_visit_alert": 3},
    "cash_counter": {"access_log": True},
}

def track_high_value_access(global_id, zone):
    visit_count = db.zone_visits.count_documents({
        "visitor_id": get_visitor_id(global_id),
        "zone": zone,
        "date": today
    })
    
    if visit_count >= high_value_zones[zone]['frequent_visit_alert']:
        return {"alert": "FREQUENT_HIGH_VALUE_ACCESS", 
                "visit_count": visit_count}
```

---

## 4. 📈 Advanced Analytics

### A. Customer Journey Mapping
**Purpose:** Understand visitor flow through campus

**Implementation:**
```python
# Build journey graph
visitor_journeys = {
    "G001": [
        {"zone": "entrance", "timestamp": "10:00:00"},
        {"zone": "library", "timestamp": "10:05:23"},
        {"zone": "cafeteria", "timestamp": "11:30:15"},
        {"zone": "exit", "timestamp": "12:45:00"}
    ]
}

# Analyze common paths
def find_common_journeys():
    # Use graph clustering or sequence mining
    common_paths = [
        {"path": ["entrance", "library", "exit"], "frequency": 45},
        {"path": ["entrance", "cafeteria", "library", "exit"], "frequency": 32}
    ]
    return common_paths
```

**Visualization:**
- Sankey diagrams for flow
- Network graphs for zone connections
- Heatmaps for transition probabilities

---

### B. Conversion Rate Analysis
**Purpose:** Measure effectiveness of campus areas/services

**Metrics:**
```python
# Library conversion
total_campus_visitors = 150
library_visitors = 45
library_conversion = 45/150 = 30%

# Average time before first service interaction
avg_time_to_library = calculate_avg_time("entrance", "library")
# Result: 15 minutes average
```

---

### C. Retention & Repeat Visitor Analysis
**Purpose:** Identify regular vs one-time visitors

**Implementation:**
```python
# Track visit frequency
def analyze_visitor_frequency():
    visitor_stats = db.visitors.aggregate([
        {"$lookup": {
            "from": "visit_events",
            "localField": "_id",
            "foreignField": "visitor_id",
            "as": "visits"
        }},
        {"$project": {
            "global_id": 1,
            "first_seen": "$first_seen_at",
            "last_seen": "$last_seen_at",
            "total_visits": {"$size": "$visits"},
            "avg_dwell": {"$avg": "$visits.dwell_time"}
        }}
    ])
    
    return {
        "daily_visitors": count_by_visit_frequency(1),
        "weekly_regulars": count_by_visit_frequency(5, 7),
        "repeat_rate": regulars / total * 100
    }
```

---

### D. Demographic Estimation (Future Enhancement)
**Purpose:** Understand visitor demographics

**Features (requires additional AI models):**
- Age group estimation
- Gender classification
- Group detection (families, friends)
- Behavior classification (walking speed, posture)

**Privacy Note:** Ensure compliance with privacy regulations

---

## 5. 🚨 Real-Time Alerts & Notifications

### Alert Types to Implement:

1. **Capacity Alerts**
   - Zone over 80% capacity
   - Campus-wide occupancy limits

2. **Security Alerts**
   - Loitering in restricted areas
   - After-hours access
   - Tailgating at entrances
   - Unusual crowd formation

3. **Operational Alerts**
   - Entry/exit imbalance (>10% difference)
   - Extended dwell in bathrooms (welfare check)
   - Zero activity for extended period (system health)

### Notification Channels:
```python
def send_alert(alert_type, details):
    # Email notification
    send_email(admin_email, f"Alert: {alert_type}", details)
    
    # SMS for critical alerts
    if alert_type in ['SECURITY_BREACH', 'CAPACITY_EXCEEDED']:
        send_sms(security_team, details)
    
    # Dashboard notification
    db.notifications.insert_one({
        "type": alert_type,
        "timestamp": datetime.utcnow(),
        "details": details,
        "acknowledged": False
    })
    
    # Webhook for integration
    requests.post(webhook_url, json=details)
```

---

## 6. 📋 Reporting Dashboard Enhancements

### A. Daily Summary Report
```python
daily_report = {
    "date": "2025-10-07",
    "total_unique_visitors": 1247,
    "peak_hour": "14:00",
    "peak_occupancy": 89,
    "avg_dwell_time": "45m 23s",
    "entry_exit_balance": 0.98,  # Should be ~1.0
    "zones": {
        "library": {"visitors": 342, "avg_dwell": "67m"},
        "cafeteria": {"visitors": 589, "avg_dwell": "23m"},
        "entrance": {"visitors": 1247, "avg_dwell": "2m"}
    },
    "alerts": {
        "loitering": 3,
        "capacity_exceeded": 0,
        "restricted_access": 1
    }
}
```

---

### B. Comparative Analytics
**Compare today vs yesterday/last week/last month:**

```python
comparison_metrics = {
    "unique_visitors": {"today": 1247, "yesterday": 1189, "change": "+4.9%"},
    "avg_dwell": {"today": "45m", "yesterday": "42m", "change": "+7.1%"},
    "peak_occupancy": {"today": 89, "yesterday": 95, "change": "-6.3%"}
}
```

---

### C. Anomaly Report
```python
anomaly_report = {
    "date": "2025-10-07",
    "anomalies_detected": [
        {
            "type": "UNUSUAL_CROWD",
            "time": "14:30",
            "zone": "parking_lot",
            "count": 145,
            "expected": 50,
            "severity": "HIGH"
        },
        {
            "type": "AFTER_HOURS_ACTIVITY",
            "time": "22:15",
            "visitor_count": 3,
            "cameras": ["cam1", "cam3"],
            "severity": "MEDIUM"
        }
    ]
}
```

---

## 7. 🎯 Zone-Based Analytics

### Define Zones with Polygons:
```python
zone_definitions = {
    "cam1": {
        "entrance": {
            "polygon": [[50, 100], [200, 100], [200, 400], [50, 400]],
            "type": "entry_point",
            "capacity": 10
        },
        "waiting_area": {
            "polygon": [[220, 150], [450, 150], [450, 380], [220, 380]],
            "type": "congregation",
            "capacity": 20,
            "normal_dwell": 180  # 3 minutes
        }
    }
}
```

### Zone Analytics:
```python
def analyze_zone_performance():
    return {
        "zone": "library",
        "metrics": {
            "total_visitors_today": 342,
            "current_occupancy": 23,
            "avg_dwell_time": "67m 15s",
            "peak_time": "14:00-15:00",
            "conversion_from_entrance": "27.4%",  # 342/1247
            "utilization_rate": "46%"  # time zone was occupied
        }
    }
```

---

## 8. 🔄 Flow & Transition Analysis

### A. Transition Matrix
**Purpose:** Understand how people move between zones

```python
transition_matrix = {
    "entrance": {"library": 0.35, "cafeteria": 0.45, "exit": 0.20},
    "library": {"cafeteria": 0.40, "exit": 0.50, "entrance": 0.10},
    "cafeteria": {"library": 0.25, "exit": 0.70, "entrance": 0.05}
}

# Detect unusual transitions
if transition["library"]["entrance"] > 0.20:
    alert("UNUSUAL_BACKFLOW")  # People going back to entrance
```

---

### B. Bottleneck Detection
**Purpose:** Identify congestion points

```python
def detect_bottlenecks():
    # Measure time between zones
    transitions = db.zone_transitions.find({
        "from_zone": "corridor_a",
        "to_zone": "corridor_b"
    })
    
    avg_transition_time = calculate_avg_time(transitions)
    
    if avg_transition_time > 120:  # 2 minutes for short corridor
        return {"bottleneck": "corridor_a_to_b", 
                "avg_time": avg_transition_time,
                "recommendation": "Check for obstruction"}
```

---

## 9. 💡 Behavioral Insights

### A. Visit Frequency Segmentation
```python
visitor_segments = {
    "first_time": {"count": 450, "avg_dwell": "35m"},
    "occasional": {"count": 320, "visits": "2-5", "avg_dwell": "52m"},
    "regular": {"count": 180, "visits": "6-15", "avg_dwell": "68m"},
    "frequent": {"count": 45, "visits": "16+", "avg_dwell": "85m"}
}
```

---

### B. Group Detection
**Purpose:** Identify groups moving together

**Implementation:**
```python
def detect_groups(frame_detections, time_window=5):
    # If 2+ people maintain close proximity for time_window
    groups = []
    for i, det1 in enumerate(frame_detections):
        for det2 in frame_detections[i+1:]:
            if calculate_distance(det1, det2) < 100:  # pixels
                if track_together_time(det1, det2) > time_window:
                    groups.append([det1['global_id'], det2['global_id']])
    return groups
```

**Use Cases:**
- Family/friend group analysis
- Event attendance estimation
- Social distancing compliance (pandemic scenarios)

---

## 10. 📊 Operational Efficiency Metrics

### A. Entry/Exit Balance
**Purpose:** Ensure count accuracy, detect system issues

```python
def check_entry_exit_balance():
    today_entries = db.visit_events.count_documents({
        "camera_id": "entrance",
        "in_time": {"$gte": start_of_day}
    })
    
    today_exits = db.visit_events.count_documents({
        "camera_id": "exit",
        "out_time": {"$ne": None},
        "out_time": {"$gte": start_of_day}
    })
    
    balance_ratio = today_exits / today_entries if today_entries > 0 else 0
    
    if balance_ratio < 0.90 or balance_ratio > 1.10:
        return {"alert": "ENTRY_EXIT_IMBALANCE", 
                "entries": today_entries, 
                "exits": today_exits,
                "ratio": balance_ratio}
```

---

### B. Camera Health Monitoring
**Purpose:** Detect camera failures or coverage gaps

```python
def monitor_camera_health():
    for camera_id in cameras:
        recent_detections = db.visit_events.count_documents({
            "camera_id": camera_id,
            "in_time": {"$gte": now - 300}  # Last 5 minutes
        })
        
        if recent_detections == 0:
            alert(f"CAMERA_INACTIVE: {camera_id}")
        
        # Check ReID quality
        reid_match_rate = calculate_match_rate(camera_id)
        if reid_match_rate < 0.70:  # Below 70% match rate
            alert(f"REID_QUALITY_DEGRADED: {camera_id}")
```

---

### C. System Performance Metrics
```python
system_health = {
    "fps_per_camera": {"cam1": 8.5, "cam2": 7.2, "cam3": 7.8},
    "avg_processing_time": "120ms",
    "reid_index_size": 1247,
    "db_query_latency": "15ms",
    "memory_usage": "2.3GB / 4GB",
    "cpu_usage": "65%",
    "reid_match_rate": "84%",
    "embedding_quality": {
        "avg_similarity": 0.88,
        "std_similarity": 0.12
    }
}
```

---

## 11. 🎓 Campus-Specific Features

### A. Class Attendance Tracking
**Purpose:** Monitor lecture hall occupancy

```python
class_analytics = {
    "lecture_hall_a": {
        "scheduled_class": "CS101",
        "scheduled_time": "14:00-15:30",
        "expected_attendance": 60,
        "actual_attendance": 54,
        "attendance_rate": "90%",
        "late_arrivals": 8,  # After 14:05
        "early_departures": 3  # Before 15:25
    }
}
```

---

### B. Library Utilization
```python
library_analytics = {
    "total_visitors_today": 342,
    "avg_study_duration": "67m",
    "peak_hours": ["14:00-16:00", "19:00-21:00"],
    "seat_utilization": {
        "zone_a": "78%",
        "zone_b": "92%",  # Hot zone
        "zone_c": "45%"   # Under-utilized
    },
    "hourly_turnover": 1.8  # People per seat per hour
}
```

---

### C. Cafeteria Queue Management
```python
queue_analytics = {
    "queue_length": 12,  # People in queue zone
    "avg_wait_time": "4m 30s",
    "service_rate": "2.5 people/min",
    "predicted_wait": "4m 48s",
    "recommendation": "OPEN_ADDITIONAL_COUNTER"  # If wait > 5 min
}
```

---

### D. Event Detection
**Purpose:** Automatically detect special events

```python
def detect_events():
    # Sudden increase in visitors
    current_count = get_current_occupancy()
    avg_count = get_historical_avg(current_hour)
    
    if current_count > avg_count * 1.5:  # 50% above normal
        return {
            "event_detected": True,
            "type": "SPECIAL_EVENT",
            "estimated_attendance": current_count,
            "start_time": estimate_event_start(),
            "affected_zones": get_crowded_zones()
        }
```

---

## 12. 🔐 Privacy-Preserving Analytics

### A. Anonymized Aggregates
```python
# Don't store individual IDs in reports, use aggregates
hourly_aggregate = {
    "hour": "14:00",
    "total_visitors": 89,
    "avg_dwell": "45m",
    "zone_distribution": {"library": 34, "cafeteria": 45, "other": 10}
    # No individual global_ids stored
}
```

---

### B. Data Retention Policy
```python
# Auto-delete detailed tracking data after N days
retention_policy = {
    "visit_events": 30,  # Keep 30 days
    "reid_assignments": 7,  # Keep 7 days
    "aggregated_stats": 365,  # Keep 1 year
    "annotated_frames": 1  # Keep 1 day
}

# Scheduled cleanup
def apply_retention_policy():
    cutoff = datetime.utcnow() - timedelta(days=retention_policy['visit_events'])
    db.visit_events.delete_many({"in_time": {"$lt": cutoff}})
```

---

## 13. 📱 Streamlit Dashboard Enhancements

### New Visualizations to Add:

1. **Real-Time Occupancy Map**
   - Grid heatmap showing current positions
   - Color-coded by density

2. **Flow Animation**
   - Animated paths showing visitor movement
   - Sankey diagram of zone transitions

3. **Alert Dashboard**
   - Real-time alert feed
   - Alert history with filters
   - Acknowledge/resolve functionality

4. **Predictive Analytics**
   - Expected peak times (next 2 hours)
   - Capacity forecast
   - Suggested staffing levels

5. **Comparison Charts**
   - Today vs yesterday
   - This week vs last week
   - Trend analysis

---

## 14. 🛠️ Implementation Priority

### Phase 1 (Quick Wins):
1. ✅ Zone-based dwell time tracking
2. ✅ Entry/exit balance monitoring
3. ✅ Peak hour detection
4. ✅ Hourly presence charts (already done!)

### Phase 2 (Medium Complexity):
1. Loitering detection
2. Zone transition analysis
3. Occupancy heatmaps
4. Alert system

### Phase 3 (Advanced):
1. Behavioral anomaly detection
2. Predictive analytics
3. Group detection
4. Customer journey mapping

---

## MongoDB Collections to Add:

```javascript
// Zone definitions
zones: {
  _id: ObjectId,
  camera_id: String,
  zone_name: String,
  polygon: [[x, y], ...],
  zone_type: String,  // entry, exit, congregation, restricted
  capacity: Number,
  metadata: Object
}

// Zone visits
zone_visits: {
  _id: ObjectId,
  visitor_id: ObjectId,
  zone_name: String,
  camera_id: String,
  entry_time: ISODate,
  exit_time: ISODate,
  dwell_seconds: Number
}

// Alerts
alerts: {
  _id: ObjectId,
  alert_type: String,
  severity: String,  // LOW, MEDIUM, HIGH, CRITICAL
  timestamp: ISODate,
  camera_id: String,
  zone: String,
  visitor_id: ObjectId,
  details: Object,
  acknowledged: Boolean,
  acknowledged_by: String,
  acknowledged_at: ISODate
}

// Occupancy snapshots (for heatmaps)
occupancy_snapshots: {
  _id: ObjectId,
  timestamp: ISODate,
  camera_id: String,
  grid_data: [[count, count, ...], [count, count, ...]],  // 10x10 grid
  total_count: Number
}

// Transitions
zone_transitions: {
  _id: ObjectId,
  visitor_id: ObjectId,
  from_zone: String,
  to_zone: String,
  transition_time: ISODate,
  duration_seconds: Number,
  path: [String]  // Ordered list of zones visited
}
```

---

## API Endpoints to Add:

```python
# Zone analytics
@app.get("/zones/{zone_name}/analytics")
def get_zone_analytics(zone_name: str, date: str = None)

# Alerts
@app.get("/alerts/active")
def get_active_alerts()

@app.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str)

# Heatmap data
@app.get("/heatmap/{camera_id}")
def get_heatmap_data(camera_id: str, hour: int = None)

# Flow analysis
@app.get("/flow/transitions")
def get_zone_transitions(start_date: str, end_date: str)

# Predictions
@app.get("/predictions/occupancy")
def predict_occupancy(hours_ahead: int = 2)

# Anomalies
@app.get("/anomalies/detect")
def detect_anomalies(sensitivity: float = 3.0)

# Comparative analytics
@app.get("/compare")
def compare_periods(period1: str, period2: str)
```

---

## Quick Win: Entry/Exit Balance Monitor

Add this to your Streamlit dashboard NOW:

```python
st.subheader("🚪 Entry/Exit Balance")
try:
    db = get_mongo_db()
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)
    
    # Count unique entries and exits
    all_visits = list(db.visit_events.find({"in_time": {"$gte": start}}))
    
    total_entries = len(all_visits)
    total_exits = len([v for v in all_visits if v.get('out_time') is not None])
    currently_inside = total_entries - total_exits
    balance_ratio = total_exits / total_entries if total_entries > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Entries", total_entries)
    col2.metric("Exits", total_exits)
    col3.metric("Currently Inside", currently_inside)
    col4.metric("Balance Ratio", f"{balance_ratio:.2%}", 
                delta="Normal" if 0.85 < balance_ratio < 1.15 else "⚠️ Check")
    
    if balance_ratio < 0.85:
        st.warning("⚠️ More entries than exits - possible counting issue or people still inside")
    elif balance_ratio > 1.15:
        st.warning("⚠️ More exits than entries - possible missed entries or system restart")
        
except Exception as e:
    st.error(f"Error: {e}")
```

---

## Summary

**Highest ROI Features to Implement Next:**

1. **Zone-based analytics** (library, cafeteria occupancy)
2. **Entry/exit balance** (detect leakage/errors)
3. **Loitering detection** (security)
4. **Peak hour analysis** (already partially done)
5. **Heatmaps** (visual engagement)
6. **Alert system** (proactive monitoring)

**For Monetary Leakage:**
- Entry/exit discrepancy tracking
- High-value zone monitoring
- Dwell-without-transaction detection (needs POS integration)

**For System Health:**
- Camera activity monitoring
- ReID match rate tracking
- Processing speed metrics
- Database query performance

---

Would you like me to implement any of these features? I can start with the entry/exit balance dashboard widget as a quick win!

