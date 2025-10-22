# MongoDB Migration Complete ✅

## Summary

The YOLOv11 Retail Analytics system has been **completely migrated from SQLAlchemy/SQLite to MongoDB**.

---

## What Was Removed

### Files Deleted:
- ❌ `src/core/storage/db.py` - SQLAlchemy database configuration
- ❌ `src/core/storage/models.py` - SQLAlchemy ORM models

### Dependencies Removed:
- ❌ `SQLAlchemy` (from requirements.txt and Dockerfile)
- ❌ `alembic` (from requirements.txt and Dockerfile)

### Documentation Updated:
- ✅ `README.md` - Updated architecture diagrams and descriptions
- ✅ `RUNNING_SERVICES.md` - Changed database references and query examples
- ✅ `START_GUIDE.md` - Updated troubleshooting and next steps
- ✅ `TIME_TRACKING_GUIDE.md` - Updated data persistence info
- ✅ `solution_propose.txt` - Updated proposal text

---

## Current MongoDB Setup

### Database Configuration:
```yaml
Environment Variables:
  - MONGO_URI=mongodb://mongo:27017
  - MONGO_DB=yolov11
  - USE_MONGO=1
```

### MongoDB Collections:

#### 1. **visitors**
```javascript
{
  _id: ObjectId,
  global_id: String,        // Unique global ID (e.g., "G1759802388_cam1_1")
  first_seen_at: ISODate,   // First detection timestamp
  last_seen_at: ISODate     // Last seen timestamp
}
```
**Indexes:**
- `global_id` (unique)
- `last_seen_at`

#### 2. **visit_events**
```javascript
{
  _id: ObjectId,
  visitor_id: ObjectId,     // Reference to visitors._id
  camera_id: String,        // Camera identifier
  in_time: ISODate,         // Entry time
  out_time: ISODate,        // Exit time (null if still active)
  global_id: String         // Redundant global_id for quick queries
}
```
**Indexes:**
- `visitor_id` + `camera_id`
- `in_time`
- `out_time`

#### 3. **activity_events** (Reserved for future use)
```javascript
{
  _id: ObjectId,
  visitor_id: ObjectId,
  zone: String,
  start_time: ISODate,
  end_time: ISODate,
  dwell_seconds: Float
}
```

---

## MongoDB Access

### Via MongoDB Shell:
```bash
# Connect to MongoDB
docker exec yolov11-mongo mongosh yolov11

# Count visitors
docker exec yolov11-mongo mongosh yolov11 --eval "db.visitors.countDocuments({})"

# View recent visitors
docker exec yolov11-mongo mongosh yolov11 --eval "db.visitors.find().limit(5).toArray()"
```

### Via Python:
```python
from core.storage.mongo import get_mongo_db

db = get_mongo_db()

# Count visitors
count = db.visitors.count_documents({})

# Get all visitors
visitors = list(db.visitors.find())

# Get visit events
events = list(db.visit_events.find({"out_time": None}))
```

### Via API:
```bash
# Get statistics
curl http://localhost:8000/stats

# Get dwell statistics
curl http://localhost:8000/dwell-stats

# Get hourly presence
curl http://localhost:8000/presence-hourly
```

---

## All Components Using MongoDB

1. **Pipeline** (`src/core/pipeline/multicam.py`)
   - Creates/updates visitors on ReID assignments
   - Logs visit events for each camera

2. **FastAPI** (`src/api/main.py`)
   - All analytics endpoints query MongoDB
   - Real-time statistics aggregation

3. **Streamlit** (`src/app/streamlit_app.py`)
   - Fetches visitor/event data from MongoDB
   - Displays dwell insights and hourly presence

4. **Scheduler** (`scripts/scheduler_reset.py`)
   - Daily reset drops MongoDB collections

---

## Verification

Run this to confirm no SQL references remain:
```bash
cd /home/vinsent_120232/proj/yolov11
grep -ri "mysql\|sqlalchemy\|sqlite" --include="*.py" --include="*.yml" 2>/dev/null | grep -v "mongo_data"
```

Expected output: ✅ No matches (clean)

---

## Migration Date
**Completed:** October 7, 2025

**Database Type:** MongoDB 6  
**Storage Engine:** WiredTiger  
**Data Location:** `./mongo_data/` (persisted volume)

---

## Next Steps

1. **Monitor MongoDB performance:**
   ```bash
   docker exec yolov11-mongo mongosh yolov11 --eval "db.stats()"
   ```

2. **Set up MongoDB backups:**
   ```bash
   docker exec yolov11-mongo mongodump --db yolov11 --out /backup
   ```

3. **Scale if needed:**
   - Add MongoDB replicas for high availability
   - Configure sharding for large datasets

**✅ System is now 100% MongoDB-powered!**
