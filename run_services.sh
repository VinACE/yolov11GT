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
    
    echo "⏳ Waiting for container to be ready..."
    # Wait for container to be fully ready (max 30 seconds)
    for i in {1..30}; do
        if docker exec yolov11-cpu python3 --version &>/dev/null; then
            echo "✅ Container ready!"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            echo "⚠️  Container taking longer than expected. Continuing anyway..."
        fi
    done
    echo ""
fi

# Ensure FaceNet is installed (critical for hybrid ReID)
echo "🔍 Checking FaceNet installation..."
if docker exec yolov11-cpu python3 -c "import facenet_pytorch" 2>/dev/null; then
    echo "✅ FaceNet is available"
else
    echo "⚠️  FaceNet not found. Installing..."
    docker exec yolov11-cpu pip install facenet-pytorch --quiet
    if [ $? -eq 0 ]; then
        echo "✅ FaceNet installed successfully"
    else
        echo "❌ FaceNet installation failed! ReID may not work properly."
    fi
fi
echo ""

# Ask user if they want to reset the database
echo "🗄️  Database Reset Options:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
read -p "Do you want to reset the database and clear outputs? (y/n): " reset_choice

if [[ "$reset_choice" =~ ^[Yy]$ ]]; then
    echo ""
    echo "🧹 Cleaning MongoDB 'yolov11' and clearing /app/outputs..."
    docker exec -i yolov11-mongo mongosh --quiet --eval "db.getSiblingDB('yolov11').dropDatabase()" || true
    docker-compose -f $COMPOSE_FILE exec -T yolov11 bash -lc "rm -rf /app/outputs/* || true; mkdir -p /app/outputs" || true
    echo "✅ Database and outputs cleared."
    echo ""
else
    echo ""
    echo "⏩ Keeping existing database and outputs."
    echo ""
    # Show current stats
    visitor_count=$(docker exec -i yolov11-mongo mongosh --quiet --eval "db.getSiblingDB('yolov11').visitors.countDocuments({})" 2>/dev/null || echo "0")
    event_count=$(docker exec -i yolov11-mongo mongosh --quiet --eval "db.getSiblingDB('yolov11').visit_events.countDocuments({})" 2>/dev/null || echo "0")
    echo "📊 Current Database Stats:"
    echo "   Visitors: $visitor_count"
    echo "   Events: $event_count"
    echo ""
fi

# Menu
echo "Select service to run:"
echo "1) FastAPI Backend (port 8000)"
echo "2) Streamlit Dashboard (port 8501)"
echo "3) Pipeline Runner (requires camera config)"
echo "4) Daily Reset Scheduler (12 PM IST)"
echo "5) Run Quick Test (YOLO + MongoDB + ReID)"
echo "6) Start All Services (API + Streamlit + Pipeline)"
echo "7) View Logs"
echo "8) Check System Status"
echo "9) Stop All"
echo ""
read -p "Enter choice [1-9]: " choice

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
from src.core.storage.mongo import get_mongo_db, upsert_visitor, insert_visit_event
from datetime import datetime
import numpy as np

print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
print('1️⃣  Testing YOLOv11 detector...')
detector = YoloV11Detector()
dummy_frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
detections = detector.detect(dummy_frame)
print(f'   ✅ Detector working! Found {len(detections)} detections')

print('')
print('2️⃣  Testing MongoDB connection...')
db = get_mongo_db()
mv = upsert_visitor(db, 'TEST_001', datetime.utcnow(), datetime.utcnow())
insert_visit_event(db, mv.get('_id'), 'test_cam', datetime.utcnow(), global_id='TEST_001')
print('   ✅ MongoDB working! Test visitor/event created')

print('')
print('3️⃣  Testing ReID embedders...')
try:
    from src.core.reid.osnet_embedder import OSNetEmbedder
    osnet = OSNetEmbedder()
    test_crop = np.random.randint(0, 255, (128, 64, 3), dtype=np.uint8)
    emb = osnet.get_embedding(test_crop)
    print(f'   ✅ OSNet working! Embedding shape: {emb.shape}')
except Exception as e:
    print(f'   ⚠️  OSNet error: {e}')

try:
    from src.core.reid.facenet_embedder import FaceNetEmbedder
    facenet = FaceNetEmbedder()
    emb = facenet.get_embedding(test_crop)
    print(f'   ✅ FaceNet working! Embedding shape: {emb.shape}')
except Exception as e:
    print(f'   ⚠️  FaceNet error: {e}')

print('')
print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
print('🎉 All core components tested! System is ready.')
print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
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
        sleep 2

        echo ""
        echo "🔍 Verifying services started..."
        
        # Check FastAPI
        if docker exec yolov11-cpu ps aux | grep -q "[u]vicorn"; then
            echo "   ✅ FastAPI running"
        else
            echo "   ❌ FastAPI failed to start"
        fi
        
        # Check Streamlit
        if docker exec yolov11-cpu ps aux | grep -q "[s]treamlit run"; then
            echo "   ✅ Streamlit running"
        else
            echo "   ❌ Streamlit failed to start"
        fi
        
        # Check Pipeline
        if docker exec yolov11-cpu ps aux | grep -q "[r]un_pipeline"; then
            echo "   ✅ Pipeline running"
        else
            echo "   ⚠️  Pipeline may not have started (check if cameras configured)"
        fi

        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📖 API: http://localhost:8000/docs"
        echo "📊 Dashboard: http://localhost:8501"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ;;
    7)
        echo "📋 Container Logs:"
        docker-compose -f $COMPOSE_FILE logs --tail=50 -f yolov11
        ;;
    8)
        echo "🔍 System Status Check"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        # Check containers
        echo "📦 Container Status:"
        if docker ps | grep -q yolov11-cpu; then
            echo "   ✅ yolov11-cpu: Running"
        else
            echo "   ❌ yolov11-cpu: Not running"
        fi
        
        if docker ps | grep -q yolov11-mongo; then
            echo "   ✅ yolov11-mongo: Running"
        else
            echo "   ❌ yolov11-mongo: Not running"
        fi
        echo ""
        
        # Check running processes
        echo "🔧 Service Processes:"
        if docker exec yolov11-cpu ps aux 2>/dev/null | grep -q "[u]vicorn"; then
            echo "   ✅ FastAPI (uvicorn) - http://localhost:8000"
        else
            echo "   ❌ FastAPI not running"
        fi
        
        if docker exec yolov11-cpu ps aux 2>/dev/null | grep -q "[s]treamlit run"; then
            echo "   ✅ Streamlit - http://localhost:8501"
        else
            echo "   ❌ Streamlit not running"
        fi
        
        if docker exec yolov11-cpu ps aux 2>/dev/null | grep -q "[r]un_pipeline"; then
            echo "   ✅ Pipeline (run_pipeline.py)"
        else
            echo "   ⚠️  Pipeline not running"
        fi
        echo ""
        
        # Check database
        echo "🗄️  Database Status:"
        visitor_count=$(docker exec -i yolov11-mongo mongosh --quiet --eval "db.getSiblingDB('yolov11').visitors.countDocuments({})" 2>/dev/null || echo "Error")
        event_count=$(docker exec -i yolov11-mongo mongosh --quiet --eval "db.getSiblingDB('yolov11').visit_events.countDocuments({})" 2>/dev/null || echo "Error")
        
        if [[ "$visitor_count" != "Error" ]]; then
            echo "   ✅ MongoDB connected"
            echo "      Visitors: $visitor_count"
            echo "      Events: $event_count"
        else
            echo "   ❌ MongoDB connection failed"
        fi
        echo ""
        
        # Check dependencies
        echo "🔬 Key Dependencies:"
        if docker exec yolov11-cpu python3 -c "import torch; print('   ✅ PyTorch:', torch.__version__)" 2>/dev/null; then
            :
        else
            echo "   ❌ PyTorch not available"
        fi
        
        if docker exec yolov11-cpu python3 -c "import torchreid; print('   ✅ OSNet (torchreid)')" 2>/dev/null; then
            :
        else
            echo "   ❌ OSNet not available"
        fi
        
        if docker exec yolov11-cpu python3 -c "import facenet_pytorch; print('   ✅ FaceNet (facenet-pytorch)')" 2>/dev/null; then
            :
        else
            echo "   ⚠️  FaceNet not available (install with option 5 or rebuild_with_facenet.sh)"
        fi
        
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ;;
    9)
        echo "🛑 Stopping all services..."
        docker-compose -f $COMPOSE_FILE down
        echo "✅ All services stopped"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac
