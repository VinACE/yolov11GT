#!/bin/bash
# Quick fix for MongoDB container with no IP address
# This usually indicates the MongoDB container is crashing or not starting properly

echo "🔧 MongoDB 'No IP' Quick Fix"
echo "============================"
echo ""

# Step 1: Check current status
echo "Step 1: Checking current MongoDB container status..."
MONGO_STATE=$(docker inspect yolov11-mongo --format '{{.State.Status}}' 2>/dev/null)
echo "   Current state: ${MONGO_STATE:-CONTAINER NOT FOUND}"
echo ""

if [ "$MONGO_STATE" = "running" ]; then
    echo "   Container shows as 'running' but has no IP."
    echo "   This usually means networking is broken."
fi

# Step 2: Get logs before stopping
echo "Step 2: Capturing MongoDB logs for diagnosis..."
docker logs yolov11-mongo --tail 100 > /tmp/mongo_debug_logs.txt 2>&1
if [ -s /tmp/mongo_debug_logs.txt ]; then
    echo "   ✅ Logs saved to /tmp/mongo_debug_logs.txt"
    echo ""
    echo "   📜 Last 20 lines:"
    tail -20 /tmp/mongo_debug_logs.txt | sed 's/^/      /'
else
    echo "   ⚠️  No logs available (container might not have started)"
fi
echo ""

# Step 3: Check if port is in use
echo "Step 3: Checking if port 27017 is in use..."
if command -v lsof &> /dev/null; then
    PORT_CHECK=$(sudo lsof -i :27017 2>/dev/null || lsof -i :27017 2>/dev/null)
    if [ -n "$PORT_CHECK" ]; then
        echo "   ⚠️  Port 27017 is in use:"
        echo "$PORT_CHECK" | sed 's/^/      /'
        echo ""
        read -p "   Kill the process using port 27017? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            PID=$(echo "$PORT_CHECK" | awk 'NR==2 {print $2}')
            sudo kill -9 "$PID" 2>/dev/null && echo "   ✅ Process killed"
        fi
    else
        echo "   ✅ Port 27017 is free"
    fi
else
    echo "   ⚠️  lsof not installed, skipping port check"
fi
echo ""

# Step 4: Check mongo_data directory
echo "Step 4: Checking mongo_data directory..."
if [ -d "./mongo_data" ]; then
    echo "   📁 mongo_data exists"
    ls -ld ./mongo_data | sed 's/^/      /'
    MONGO_DATA_SIZE=$(du -sh ./mongo_data 2>/dev/null | cut -f1)
    echo "   Size: $MONGO_DATA_SIZE"
    echo ""
    read -p "   Remove mongo_data and start fresh? This will delete all data! (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   → Stopping containers..."
        docker-compose -f docker-compose.yolov11.yml down
        echo "   → Removing mongo_data..."
        rm -rf ./mongo_data
        echo "   ✅ mongo_data removed"
    fi
else
    echo "   ⚠️  mongo_data directory doesn't exist (will be created on start)"
fi
echo ""

# Step 5: Full Docker cleanup
echo "Step 5: Performing full Docker cleanup..."
echo "   → Stopping all containers..."
docker-compose -f docker-compose.yolov11.yml down
echo "   → Pruning Docker networks..."
docker network prune -f
echo "   → Pruning stopped containers..."
docker container prune -f
echo "   ✅ Cleanup complete"
echo ""

# Step 6: Restart with verbose logging
echo "Step 6: Starting containers with verbose logging..."
echo "   → Starting MongoDB first..."
docker-compose -f docker-compose.yolov11.yml up -d mongo
echo "   → Waiting 15 seconds for MongoDB to initialize..."
for i in {15..1}; do
    echo -ne "      $i...\r"
    sleep 1
done
echo ""

# Step 7: Check MongoDB status
echo "Step 7: Checking MongoDB status after restart..."
MONGO_STATE=$(docker inspect yolov11-mongo --format '{{.State.Status}}' 2>/dev/null)
MONGO_IP=$(docker inspect yolov11-mongo -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)

echo "   State: ${MONGO_STATE:-NOT FOUND}"
echo "   IP: ${MONGO_IP:-NOT FOUND}"

if [ -z "$MONGO_IP" ]; then
    echo ""
    echo "   ❌ MongoDB still has no IP!"
    echo ""
    echo "   📜 Current MongoDB logs:"
    docker logs yolov11-mongo --tail 50 2>&1 | sed 's/^/      /'
    echo ""
    echo "   💡 Manual troubleshooting steps:"
    echo "      1. Check Docker daemon: sudo systemctl status docker"
    echo "      2. Check Docker version: docker --version"
    echo "      3. Try running MongoDB directly:"
    echo "         docker run -d --name test-mongo -p 27017:27017 mongo:6"
    echo "      4. Check for disk space: df -h"
    echo "      5. Check Docker logs: journalctl -u docker -n 50"
    exit 1
else
    echo ""
    echo "   ✅ MongoDB has IP address!"
    echo "   → Starting remaining containers..."
    docker-compose -f docker-compose.yolov11.yml up -d
    sleep 5
    echo ""
    echo "   ✅ All containers started successfully!"
    echo ""
    echo "   📊 Final status:"
    docker-compose -f docker-compose.yolov11.yml ps
fi

echo ""
echo "🎉 Fix complete! Run ./check_mongo.sh to verify the connection."


