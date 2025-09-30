# 🚀 Quick Start Guide - Retail Analytics System

## Prerequisites
- Docker and Docker Compose installed
- At least 4GB RAM available
- Ports 8000, 8501, 3306 free on your host

## Step-by-Step Setup

### Step 1: Build the Docker Image
```bash
cd /home/vinsent_120232/proj/yolov11
docker-compose -f docker-compose.yolov11.yml build
```
This will take 5-10 minutes on first build (installing all dependencies).

### Step 2: Start the Container
```bash
docker-compose -f docker-compose.yolov11.yml up -d
```
Check if it's running:
```bash
docker ps | grep yolov11
```

### Step 3: Start the FastAPI Backend (Terminal 1)
```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 bash -c "cd /app && python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
```

**Test it:**
Open a new terminal and run:
```bash
curl http://localhost:8000/health
# Should return: {"status":"ok"}

curl http://localhost:8000/stats
# Should return: {"active_visitors":0,"total_today":0}
```

### Step 4: Start Streamlit Dashboard (Terminal 2)
Open a **new terminal** and run:
```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 bash -c "cd /app && streamlit run src/app/streamlit_app.py --server.address 0.0.0.0 --server.port 8501"
```

**Access the dashboard:**
Open your browser: http://localhost:8501

### Step 5: Run the Pipeline (Terminal 3)
Before running, you need video sources. You can:

**Option A: Use test videos**
Place video files in the `data/` directory, then update `scripts/run_pipeline.py`:
```python
cameras = {
    "cam1": "/app/data/your_video1.mp4",
    "cam2": "/app/data/your_video2.mp4",
}
```

**Option B: Use RTSP camera streams**
```python
cameras = {
    "entrance": "rtsp://username:password@192.168.1.10:554/stream1",
    "checkout": "rtsp://username:password@192.168.1.11:554/stream1",
}
```

Then run:
```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 bash -c "cd /app && python scripts/run_pipeline.py"
```

### Step 6: (Optional) Daily Reset Scheduler (Terminal 4)
To enable automatic daily reset at 12:00 PM IST:
```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 bash -c "cd /app && python scripts/scheduler_reset.py"
```

## 🎯 Quick Test Without Cameras

If you don't have videos yet, test the system with this simple script:

```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 python3 -c "
from src.core.detection.yolo import YoloV11Detector
from src.core.storage.db import init_db, get_db
from src.core.storage.models import Visitor, VisitEvent
from datetime import datetime
import numpy as np

# Initialize DB
init_db()

# Test detector
detector = YoloV11Detector()
dummy_frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
detections = detector.detect(dummy_frame)
print(f'✅ Detector working! Found {len(detections)} detections')

# Test database
with get_db() as db:
    visitor = Visitor(global_id='TEST_001', first_seen_at=datetime.utcnow(), last_seen_at=datetime.utcnow())
    db.add(visitor)
    db.commit()
    print('✅ Database working! Test visitor created')
"
```

## 📊 Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| FastAPI | http://localhost:8000 | REST API |
| FastAPI Docs | http://localhost:8000/docs | Interactive API documentation |
| Streamlit | http://localhost:8501 | Dashboard UI |
| MySQL | localhost:3306 | Database (if using MySQL) |

## 🔧 Troubleshooting

### Container won't start
```bash
docker-compose -f docker-compose.yolov11.yml logs yolov11
```

### API not accessible
```bash
# Check if API process is running
docker-compose -f docker-compose.yolov11.yml exec yolov11 ps aux | grep uvicorn
```

### Import errors
```bash
# Set PYTHONPATH
docker-compose -f docker-compose.yolov11.yml exec yolov11 bash -c "export PYTHONPATH=/app:$PYTHONPATH && python scripts/run_pipeline.py"
```

### Database errors
```bash
# Reinitialize database
docker-compose -f docker-compose.yolov11.yml exec yolov11 python3 -c "from src.core.storage.db import init_db; init_db(); print('DB initialized')"
```

## 🛑 Stop Everything

```bash
# Stop containers
docker-compose -f docker-compose.yolov11.yml down

# Stop and remove volumes (⚠️ deletes data)
docker-compose -f docker-compose.yolov11.yml down -v
```

## 📝 Next Steps

1. **Replace stubs with production models:**
   - `src/core/segmentation/sam.py` - Add real SAM model
   - `src/core/tracking/tracker.py` - Integrate DeepSORT/ByteTrack
   - `src/core/reid/embedding.py` - Use trained ReID model

2. **Add zone definitions:**
   - Edit `src/core/pipeline/multicam.py`
   - Define polygons for store zones (entrance, checkout, etc.)

3. **Enhance dashboard:**
   - Edit `src/app/streamlit_app.py`
   - Add charts, heatmaps, customer journey visualization

4. **Switch to MySQL (optional):**
   - Update `src/core/storage/db.py` to use MySQL connection
   - Use credentials from docker-compose MySQL service
