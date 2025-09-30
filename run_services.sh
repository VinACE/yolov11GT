#!/bin/bash
# Helper script to run all services

set -e

COMPOSE_FILE="docker-compose.yolov11.yml"

echo "🚀 Retail Analytics System - Service Launcher"
echo "=============================================="
echo ""

# Check if container is running
if ! docker ps | grep -q yolov11-cpu; then
    echo "⚠️  Container not running. Starting..."
    docker-compose -f $COMPOSE_FILE up -d
    sleep 3
fi

# Menu
echo "Select service to run:"
echo "1) FastAPI Backend (port 8000)"
echo "2) Streamlit Dashboard (port 8501)"
echo "3) Pipeline Runner (requires camera config)"
echo "4) Daily Reset Scheduler (12 PM IST)"
echo "5) Run Quick Test (no cameras needed)"
echo "6) Start All Services (API + Streamlit)"
echo "7) View Logs"
echo "8) Stop All"
echo ""
read -p "Enter choice [1-8]: " choice

case $choice in
    1)
        echo "🔥 Starting FastAPI on http://localhost:8000"
        echo "📖 API Docs: http://localhost:8000/docs"
        docker-compose -f $COMPOSE_FILE exec yolov11 bash -c "pkill -f 'uvicorn' || true; cd /app && python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
        ;;
    2)
        echo "📊 Starting Streamlit on http://localhost:8501"
        docker-compose -f $COMPOSE_FILE exec yolov11 bash -c "pkill -f 'streamlit run' || true; cd /app && streamlit run src/app/streamlit_app.py --server.address 0.0.0.0 --server.port 8501"
        ;;
    3)
        echo "🎥 Starting Pipeline Runner"
        echo "⚠️  Make sure you've configured camera sources in scripts/run_pipeline.py"
        docker-compose -f $COMPOSE_FILE exec yolov11 bash -c "pkill -f run_pipeline || true; cd /app && python scripts/run_pipeline.py"
        ;;
    4)
        echo "⏰ Starting Daily Reset Scheduler (12:00 PM IST)"
        docker-compose -f $COMPOSE_FILE exec yolov11 bash -c "cd /app && python scripts/scheduler_reset.py"
        ;;
    5)
        echo "🧪 Running Quick Test..."
        docker-compose -f $COMPOSE_FILE exec yolov11 python3 -c "
from src.core.detection.yolo import YoloV11Detector
from src.core.storage.db import init_db, get_db
from src.core.storage.models import Visitor, VisitEvent
from datetime import datetime
import numpy as np

print('Initializing database...')
init_db()

print('Testing YOLOv11 detector...')
detector = YoloV11Detector()
dummy_frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
detections = detector.detect(dummy_frame)
print(f'✅ Detector working! Found {len(detections)} detections')

print('Testing database connection...')
with get_db() as db:
    visitor = Visitor(global_id='TEST_001', first_seen_at=datetime.utcnow(), last_seen_at=datetime.utcnow())
    db.add(visitor)
    db.commit()
    print('✅ Database working! Test visitor created')

print('')
print('🎉 All tests passed! System is ready.')
"
        ;;
    6)
        echo "🚀 Restarting container and starting all services..."
        # Ensure any previous app processes are stopped and container proxy ports are clean
        docker-compose -f $COMPOSE_FILE exec yolov11 bash -c "pkill -f 'uvicorn' || true; pkill -f 'streamlit run' || true; pkill -f run_pipeline || true" || true
        docker-compose -f $COMPOSE_FILE up -d --force-recreate yolov11
        sleep 3

        echo "Starting FastAPI in background..."
        docker-compose -f $COMPOSE_FILE exec -d yolov11 bash -c "cd /app && python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
        sleep 2

        echo "Starting Streamlit in background (8501)..."
        docker-compose -f $COMPOSE_FILE exec -d yolov11 bash -c "cd /app && streamlit run src/app/streamlit_app.py --server.address 0.0.0.0 --server.port 8501"
        sleep 2

        echo "Starting Pipeline in background..."
        docker-compose -f $COMPOSE_FILE exec -d yolov11 bash -c "cd /app && python scripts/run_pipeline.py"

        echo "📖 API: http://localhost:8000/docs"
        echo "📊 Dashboard: http://localhost:8501"
        ;;
    7)
        echo "📋 Container Logs:"
        docker-compose -f $COMPOSE_FILE logs --tail=50 -f yolov11
        ;;
    8)
        echo "🛑 Stopping all services..."
        docker-compose -f $COMPOSE_FILE down
        echo "✅ All services stopped"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac
