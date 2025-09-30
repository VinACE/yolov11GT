# ✅ Your Retail Analytics System is RUNNING!

## 🎊 Status: ALL SYSTEMS OPERATIONAL

### Running Services

| Service | Status | URL | Purpose |
|---------|--------|-----|---------|
| **FastAPI** | ✅ RUNNING | http://localhost:8000 | REST API Backend |
| **FastAPI Docs** | ✅ RUNNING | http://localhost:8000/docs | Interactive API Docs |
| **Streamlit** | ✅ RUNNING | http://localhost:8501 | Analytics Dashboard |
| **YOLOv11** | ✅ READY | - | Person Detection |
| **SQLite DB** | ✅ READY | /app/analytics.db | Data Storage |

---

## 🌐 Access Your System

### 1. API Documentation (Swagger UI)
```
http://localhost:8000/docs
```
- Try the `/health` endpoint
- Try the `/stats` endpoint
- Explore the `/reset-daily` endpoint

### 2. Streamlit Dashboard
```
http://localhost:8501
```
- View active visitors count
- See total visits today
- (More features coming as you extend it!)

---

## 📡 Test the API

### Health Check
```bash
curl http://localhost:8000/health
# Response: {"status":"ok"}
```

### Get Stats
```bash
curl http://localhost:8000/stats
# Response: {"active_visitors":0,"total_today":0}
```

### Manual Daily Reset
```bash
curl -X POST http://localhost:8000/reset-daily
# Response: {"status":"reset_ok"}
```

---

## 🎥 Next: Run the Pipeline with Cameras

###  Option 1: Test with Sample Videos

1. Put video files in the `data/` folder:
```bash
cp /path/to/your/video.mp4 /home/vinsent_120232/proj/yolov11/data/
```

2. Edit `scripts/run_pipeline.py`:
```python
cameras = {
    "entrance": "/app/data/video.mp4",
    "checkout": "/app/data/another_video.mp4",
}
```

3. Run the pipeline:
```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 bash -c "cd /app && python scripts/run_pipeline.py"
```

### Option 2: Use RTSP Cameras

Edit `scripts/run_pipeline.py`:
```python
cameras = {
    "entrance": "rtsp://user:pass@192.168.1.10:554/stream1",
    "checkout": "rtsp://user:pass@192.168.1.11:554/stream1",
}
```

Then run it.

---

## ⏰ Enable Daily Reset at 12:00 PM IST

In a new terminal:
```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 bash -c "cd /app && python scripts/scheduler_reset.py"
```

This will keep running and auto-reset data at noon every day.

---

## 🔍 Monitor Logs

### API Logs
```bash
docker-compose -f docker-compose.yolov11.yml logs -f yolov11 | grep uvicorn
```

### Streamlit Logs
```bash
docker-compose -f docker-compose.yolov11.yml logs -f yolov11 | grep streamlit
```

### All Container Logs
```bash
docker-compose -f docker-compose.yolov11.yml logs -f yolov11
```

---

##  🛠️ Manage Services

### Stop Everything
```bash
docker-compose -f docker-compose.yolov11.yml down
```

### Restart Services
```bash
# Inside the container, restart processes
docker-compose -f docker-compose.yolov11.yml exec yolov11 pkill -f uvicorn
docker-compose -f docker-compose.yolov11.yml exec yolov11 pkill -f streamlit

# Then use run_services.sh to start again
./run_services.sh
```

### Check Container Status
```bash
docker-compose -f docker-compose.yolov11.yml ps
docker-compose -f docker-compose.yolov11.yml exec yolov11 ps aux | grep -E "uvicorn|streamlit"
```

---

## 📊 Database Location

Your SQLite database is stored at:
```
/app/analytics.db
```

Inside the container, you can query it:
```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 python3 -c "
from src.core.storage.db import get_db
from src.core.storage.models import Visitor, VisitEvent

with get_db() as db:
    visitors = db.query(Visitor).all()
    print(f'Total visitors in DB: {len(visitors)}')
    for v in visitors[:5]:
        print(f'  - {v.global_id}: {v.first_seen_at} to {v.last_seen_at}')
"
```

---

## 🎯 What's Next?

1. **Test with real videos** - Add MP4/AVI files to `data/`folder and run the pipeline
2. **Connect RTSP cameras** - Edit camera sources in `scripts/run_pipeline.py`
3. **Enhance dashboard** - Add charts, heatmaps in `src/app/streamlit_app.py`
4. **Add zone tracking** - Define store zones in `src/core/pipeline/multicam.py`
5. **Improve ReID** - Replace stub embedder with trained model
6. **Add DeepSORT** - Replace SimpleTracker with DeepSORT/ByteTrack

---

## ✅ System Components Verified

- [x] Docker container built and running
- [x] YOLOv11 detector operational
- [x] SAM segmenter stub ready
- [x] Single-camera tracker ready
- [x] ReID module with FAISS ready
- [x] SQLAlchemy database initialized
- [x] FastAPI service running
- [x] Streamlit dashboard running
- [x] All dependencies installed

**🎉 Congratulations! Your system is fully operational!**
