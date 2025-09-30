# ⏱️ Time Tracking Feature - User Guide

## Overview

The system now tracks **how long each visitor spends in the campus/premises** from their first detection to their last seen time.

---

## 📊 What Gets Tracked

For each visitor, the system records:

- **Entry Time** (`first_seen_at`) - When they were first detected
- **Last Seen Time** (`last_seen_at`) - When they were last detected
- **Time Spent** - Calculated as: `last_seen_at - first_seen_at`
- **Status** - Whether they're still in premises or have exited

---

## 🔄 How It Works

### 1. Detection & Entry
- YOLOv11 detects a person in any camera
- System creates a new `Visitor` record with:
  - `global_id` (unique identifier)
  - `first_seen_at` (entry timestamp)
  - `last_seen_at` (initially same as entry time)

### 2. Continuous Tracking
- As long as the person is visible in any camera:
  - ReID keeps matching them to the same global ID
  - `last_seen_at` keeps updating to current timestamp
  
### 3. Exit Detection
- When person is no longer detected for some time:
  - `last_seen_at` remains at the last detection timestamp
  - Time spent = `last_seen_at - first_seen_at`

---

## 📡 API Endpoints

### Get Time Spent for All Visitors
```bash
GET /time-spent
```

**Example:**
```bash
curl http://localhost:8000/time-spent | python3 -m json.tool
```

**Response:**
```json
{
  "visitors": [
    {
      "global_id": "G1759191668_cam1_1",
      "entry_time": "2025-09-30T05:51:08.241193",
      "exit_time": "2025-09-30T05:54:18.748564",
      "time_spent_seconds": 190.507371,
      "time_spent_formatted": "3m 10s"
    }
  ]
}
```

### Get Basic Stats
```bash
GET /stats
```

Returns:
- Active visitors (currently in premises)
- Total visits today

---

## 🖥️ Dashboard Access

### Streamlit Dashboard
Open in browser: **http://localhost:8501**

**Features:**
- 📊 Real-time visitor count
- ⏱️ Average time spent
- 📋 Detailed table with:
  - Visitor ID
  - Entry time
  - Last seen time
  - Time spent (formatted)
  - Status (in/out)
- 📥 Download report as CSV

---

## 🛠️ Command-Line Tools

### Quick Time Report
```bash
./check_time_spent.sh
```

Shows:
- List of all visitors
- Entry and exit times
- Time spent per visitor
- Average time spent

### Monitor Pipeline
```bash
./monitor_pipeline.sh
```

Real-time monitoring of:
- Pipeline status
- Active visitor count
- Total visits

---

## 📈 Example Use Cases

### 1. Retail Store Analytics
Track how long customers browse:
```python
# Cameras at entrance, aisles, checkout
cameras = {
    "entrance": "rtsp://entrance-cam/stream",
    "aisle1": "rtsp://aisle1-cam/stream",
    "checkout": "rtsp://checkout-cam/stream"
}
```

**Metrics you get:**
- Average shopping time
- Peak hours (most visitors)
- Conversion rate (entrance vs checkout)

### 2. Campus Security
Monitor visitor duration:
- Students: typical 6-8 hours
- Visitors: 1-2 hours
- Unusual patterns: <10 min or >12 hours (alerts)

### 3. Event Management
Track attendee engagement:
- Conference rooms: session duration
- Exhibition areas: booth dwell time
- Networking zones: social time

---

## 🎯 Time Format

Times are displayed in human-readable format:

| Duration | Format |
|----------|--------|
| < 1 minute | `45s` |
| 1-59 minutes | `5m 32s` |
| 1+ hours | `2h 15m 30s` |

---

## 📊 Sample Output

```
⏰ Visitor Time Tracking Report
================================

Visitor #1: G1759191668_cam1_1
  📅 Entry Time:    2025-09-30T05:51:08
  🕐 Last Seen:     2025-09-30T05:54:18
  ⏱️  Time Spent:    3m 10s

Visitor #2: G1759191674_cam1_109
  📅 Entry Time:    2025-09-30T05:51:13
  🕐 Last Seen:     2025-09-30T05:54:18
  ⏱️  Time Spent:    3m 5s

📊 Summary Statistics:
  Total Visitors:     2
  Average Time Spent: 3m 7s
```

---

## 🔧 Advanced Configuration

### Adjust Detection Timeout
Currently, visitors are marked as "exited" when not detected for a period. To adjust:

Edit `src/core/pipeline/multicam.py` to add timeout logic:
```python
TIMEOUT_SECONDS = 300  # 5 minutes

if (dt_now - visitor.last_seen_at).total_seconds() > TIMEOUT_SECONDS:
    # Mark as exited
    visit_event.out_time = visitor.last_seen_at
```

### Zone-Specific Time Tracking
To track time spent in specific zones, use the `ActivityEvent` model:
```python
# Define zones
zones = {
    "entrance": polygon_coords,
    "checkout": polygon_coords
}

# Check if person is in zone
if point_in_polygon(bbox_center, zone_polygon):
    # Create/update ActivityEvent
```

---

## 📥 Export Data

### Via Dashboard
1. Open http://localhost:8501
2. Click "📥 Download Report" button
3. Gets CSV with all visitor time data

### Via API
```bash
curl http://localhost:8000/time-spent > visitor_report.json
```

### Via Database
```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 python3 -c "
import sys; sys.path.insert(0, '/app/src')
from core.storage.db import get_db
from core.storage.models import Visitor

with get_db() as db:
    for v in db.query(Visitor).all():
        time_spent = (v.last_seen_at - v.first_seen_at).total_seconds()
        print(f'{v.global_id},{v.first_seen_at},{v.last_seen_at},{time_spent}')
" > visitors.csv
```

---

## 🚀 What's New

✅ **Added Features:**
- New `/time-spent` API endpoint
- Enhanced Streamlit dashboard with time tracking table
- Average time spent metric
- Human-readable time formatting
- CSV export functionality
- `check_time_spent.sh` command-line tool

✅ **Updated Components:**
- `src/api/main.py` - New endpoint and models
- `src/app/streamlit_app.py` - Enhanced UI with time table
- `src/core/pipeline/multicam.py` - Improved tracking logic

---

## 💡 Tips

1. **For accurate timing:** Ensure cameras cover all entry/exit points
2. **Multi-camera setup:** ReID links same person across cameras for accurate total time
3. **Real-time updates:** Dashboard auto-refreshes (or manually refresh)
4. **Historical data:** All data persists in SQLite database at `/app/analytics.db`

---

**Questions?** Check the main README.md or API docs at http://localhost:8000/docs
