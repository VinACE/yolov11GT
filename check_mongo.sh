#!/bin/bash
# MongoDB Connection Diagnostics Script

echo "🔍 MongoDB Connection Diagnostics"
echo "=================================="
echo ""

# Check if running in correct directory
if [ ! -f "docker-compose.yolov11.yml" ]; then
    echo "❌ Error: docker-compose.yolov11.yml not found"
    echo "   Please run this script from the yolov11 project directory"
    exit 1
fi

echo "1. Checking if MongoDB container exists..."
if docker ps -a | grep -q yolov11-mongo; then
    if docker ps | grep -q yolov11-mongo; then
        echo "   ✅ MongoDB container is running"
    else
        echo "   ⚠️  MongoDB container exists but is stopped"
        echo "   → Starting MongoDB..."
        docker-compose -f docker-compose.yolov11.yml up -d mongo
        sleep 5
    fi
else
    echo "   ❌ MongoDB container doesn't exist"
    echo "   → Creating and starting MongoDB..."
    docker-compose -f docker-compose.yolov11.yml up -d mongo
    sleep 5
fi

echo ""
echo "2. Checking if application container exists..."
if docker ps -a | grep -q yolov11-cpu; then
    if docker ps | grep -q yolov11-cpu; then
        echo "   ✅ Application container is running"
    else
        echo "   ⚠️  Application container exists but is stopped"
        echo "   → Starting application..."
        docker-compose -f docker-compose.yolov11.yml up -d yolov11
        sleep 3
    fi
else
    echo "   ❌ Application container doesn't exist"
    echo "   → Creating and starting application..."
    docker-compose -f docker-compose.yolov11.yml up -d
    sleep 5
fi

echo ""
echo "3. Checking network connectivity..."
MONGO_IP=$(docker inspect yolov11-mongo -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)
APP_IP=$(docker inspect yolov11-cpu -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)

echo "   MongoDB IP: ${MONGO_IP:-NOT FOUND}"
echo "   App IP: ${APP_IP:-NOT FOUND}"

if [ -z "$MONGO_IP" ] || [ -z "$APP_IP" ]; then
    echo "   ❌ One or both containers don't have IP addresses"
    
    # Check MongoDB container status
    echo ""
    echo "   📋 Checking MongoDB container status..."
    MONGO_STATE=$(docker inspect yolov11-mongo --format '{{.State.Status}}' 2>/dev/null)
    echo "   MongoDB State: ${MONGO_STATE:-UNKNOWN}"
    
    if [ "$MONGO_STATE" != "running" ]; then
        echo "   ⚠️  MongoDB container is not running!"
        echo ""
        echo "   📜 Last 30 lines of MongoDB logs:"
        docker logs yolov11-mongo --tail 30 2>&1 | sed 's/^/      /'
        echo ""
    fi
    
    # Check for volume permission issues
    if [ -d "./mongo_data" ]; then
        echo "   📁 Checking mongo_data permissions..."
        ls -ld ./mongo_data | sed 's/^/      /'
    fi
    
    echo ""
    echo "   → Restarting with fresh network..."
    docker-compose -f docker-compose.yolov11.yml down
    docker-compose -f docker-compose.yolov11.yml up -d
    sleep 10
    
    # Recheck
    MONGO_IP=$(docker inspect yolov11-mongo -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)
    APP_IP=$(docker inspect yolov11-cpu -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)
    echo "   After restart - MongoDB IP: ${MONGO_IP:-NOT FOUND}"
    echo "   After restart - App IP: ${APP_IP:-NOT FOUND}"
    
    if [ -z "$MONGO_IP" ]; then
        echo ""
        echo "   ⚠️  MongoDB still has no IP. Checking logs..."
        MONGO_STATE=$(docker inspect yolov11-mongo --format '{{.State.Status}}' 2>/dev/null)
        if [ "$MONGO_STATE" != "running" ]; then
            echo "   📜 MongoDB container logs:"
            docker logs yolov11-mongo --tail 50 2>&1 | sed 's/^/      /'
            echo ""
            echo "   💡 Possible fixes:"
            echo "      1. Check if port 27017 is already in use: sudo lsof -i :27017"
            echo "      2. Remove mongo_data directory and restart: rm -rf ./mongo_data"
            echo "      3. Check Docker daemon is running: sudo systemctl status docker"
            exit 1
        fi
    fi
fi

echo ""
echo "4. Checking if containers are on same network..."
MONGO_NET=$(docker inspect yolov11-mongo -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null)
APP_NET=$(docker inspect yolov11-cpu -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null)

echo "   MongoDB network: ${MONGO_NET:-NOT FOUND}"
echo "   App network: ${APP_NET:-NOT FOUND}"

if [ "$MONGO_NET" != "$APP_NET" ]; then
    echo "   ❌ Containers are on different networks!"
    echo "   → This is the problem. Restarting..."
    docker-compose -f docker-compose.yolov11.yml down
    docker network prune -f
    docker-compose -f docker-compose.yolov11.yml up -d
    sleep 10
    echo "   ✅ Containers restarted on same network"
else
    echo "   ✅ Both containers on same network"
fi

echo ""
echo "5. Testing hostname resolution from app container..."
if docker exec yolov11-cpu python3 -c "import socket; ip=socket.gethostbyname('mongo'); print(f'Resolved to: {ip}')" 2>/dev/null; then
    echo "   ✅ Hostname 'mongo' resolves correctly"
else
    echo "   ❌ Cannot resolve hostname 'mongo'"
    echo "   → This indicates a Docker networking issue"
    echo ""
    echo "   Attempting full reset..."
    docker-compose -f docker-compose.yolov11.yml down
    docker network prune -f
    sleep 2
    docker-compose -f docker-compose.yolov11.yml up -d
    sleep 15
    
    if docker exec yolov11-cpu python3 -c "import socket; socket.gethostbyname('mongo')" 2>/dev/null; then
        echo "   ✅ Hostname resolution fixed after reset"
    else
        echo "   ❌ Still cannot resolve. Please check Docker installation."
        exit 1
    fi
fi

echo ""
echo "6. Testing MongoDB connection from Python..."
if docker exec yolov11-cpu python3 -c "
import sys
sys.path.insert(0, '/app/src')
from pymongo import MongoClient
try:
    client = MongoClient('mongodb://mongo:27017', serverSelectionTimeoutMS=5000)
    info = client.server_info()
    print(f'✅ MongoDB version: {info[\"version\"]}')
except Exception as e:
    print(f'❌ Connection failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
    echo "   ✅ MongoDB connection successful"
else
    echo "   ⚠️  MongoDB connection failed"
    echo "   → Waiting for MongoDB to be fully ready..."
    sleep 10
    
    if docker exec yolov11-cpu python3 -c "from pymongo import MongoClient; MongoClient('mongodb://mongo:27017', serverSelectionTimeoutMS=5000).server_info()" 2>/dev/null; then
        echo "   ✅ MongoDB connection successful after waiting"
    else
        echo "   ❌ Still cannot connect to MongoDB"
        echo ""
        echo "   Checking MongoDB logs:"
        docker logs yolov11-mongo --tail 20
        exit 1
    fi
fi

echo ""
echo "7. Testing application database access..."
if docker exec yolov11-cpu python3 -c "
import sys
sys.path.insert(0, '/app/src')
from core.storage.mongo import get_mongo_db
db = get_mongo_db()
collections = db.list_collection_names()
print(f'✅ Database accessible. Collections: {collections}')
" 2>/dev/null; then
    echo "   ✅ Application can access database"
else
    echo "   ❌ Application cannot access database"
    echo "   → Check application logs:"
    docker logs yolov11-cpu --tail 20
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All checks passed! MongoDB is accessible."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 You can now start the services:"
echo "   ./run_services.sh"
echo ""
echo "📊 Or test the API:"
echo "   curl http://localhost:8000/health"
echo ""


