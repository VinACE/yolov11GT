# 🔧 Troubleshooting Guide

## Common Issues and Solutions

---

## ❌ Error: MongoDB Container Has No IP Address

### Symptoms:
- `docker ps` shows `yolov11-mongo` as "Up" (running)
- `docker inspect yolov11-mongo` shows no IP address
- Application cannot connect to MongoDB
- `check_mongo.sh` reports "MongoDB IP: NOT FOUND"

### Root Causes:
1. **MongoDB container crashing immediately** after start (restart loop)
2. **Port 27017 already in use** by another process
3. **Corrupted `mongo_data` volume** from previous failed start
4. **Docker networking bug** (rare but possible)
5. **Insufficient disk space** for MongoDB to write data

### Quick Fix:
```bash
# Run the automated fix script
./fix_mongo_no_ip.sh
```

This script will:
- Capture MongoDB logs for diagnosis
- Check if port 27017 is in use
- Optionally remove corrupted `mongo_data`
- Perform full Docker cleanup
- Restart containers with verbose monitoring

### Manual Fix Steps:

1. **Check MongoDB logs**:
   ```bash
   docker logs yolov11-mongo --tail 50
   ```
   Look for errors like:
   - `Address already in use`
   - `Permission denied`
   - `No space left on device`
   - `WiredTiger error`

2. **Check if port is in use**:
   ```bash
   sudo lsof -i :27017
   # OR
   sudo netstat -tuln | grep 27017
   ```
   If another process is using it, stop that process first.

3. **Remove corrupted data** (⚠️ **deletes all MongoDB data**):
   ```bash
   docker-compose -f docker-compose.yolov11.yml down
   rm -rf ./mongo_data
   docker-compose -f docker-compose.yolov11.yml up -d
   ```

4. **Check disk space**:
   ```bash
   df -h
   ```
   Ensure you have at least 1GB free.

5. **Full Docker reset**:
   ```bash
   docker-compose -f docker-compose.yolov11.yml down
   docker network prune -f
   docker system prune -f
   docker-compose -f docker-compose.yolov11.yml up -d
   ```

---

## ❌ Error: "Temporary failure in name resolution" for `mongo:27017`

### Error Message:
```
pymongo.errors.ServerSelectionTimeoutError: mongo:27017: [Errno -3] 
Temporary failure in name resolution
```

### Root Cause:
The application container cannot resolve the hostname `mongo` because:
1. Docker Compose networking not properly initialized
2. Containers on different networks
3. MongoDB container not running
4. DNS resolution issue in Docker

---

## ✅ Solution Steps

### Step 1: Check if MongoDB is Running

```bash
docker ps | grep mongo
```

**Expected Output:**
```
yolov11-mongo   Up X minutes   0.0.0.0:27017->27017/tcp
```

**If NOT running:**
```bash
docker-compose -f docker-compose.yolov11.yml up -d mongo
sleep 5
```

---

### Step 2: Verify Network Configuration

```bash
# Check which network the containers are on
docker inspect yolov11-cpu | grep -A 5 "Networks"
docker inspect yolov11-mongo | grep -A 5 "Networks"
```

**Both should be on the same network** (e.g., `yolov11_default`)

**If on different networks, restart:**
```bash
docker-compose -f docker-compose.yolov11.yml down
docker-compose -f docker-compose.yolov11.yml up -d
```

---

### Step 3: Test Connection from Container

```bash
# Test if 'mongo' hostname resolves
docker exec yolov11-cpu ping -c 2 mongo

# If ping not available, test with Python
docker exec yolov11-cpu python3 -c "import socket; print(socket.gethostbyname('mongo'))"
```

**Expected:** Should print MongoDB container IP (e.g., `172.21.0.2`)

---

### Step 4: Complete Reset (If Above Fails)

```bash
# Stop all containers
docker-compose -f docker-compose.yolov11.yml down

# Remove networks
docker network prune -f

# Restart with fresh network
docker-compose -f docker-compose.yolov11.yml up -d

# Wait for MongoDB to be ready
sleep 10

# Verify MongoDB is accessible
docker exec yolov11-cpu python3 -c "from pymongo import MongoClient; c = MongoClient('mongodb://mongo:27017'); print('✅ Connected:', c.server_info()['version'])"
```

---

## 🔍 Quick Diagnosis Script

Your colleague can run this to diagnose the issue:

```bash
#!/bin/bash
echo "🔍 MongoDB Connection Diagnostics"
echo "=================================="
echo ""

echo "1. Checking if MongoDB container is running..."
if docker ps | grep -q yolov11-mongo; then
    echo "   ✅ MongoDB container is running"
else
    echo "   ❌ MongoDB container is NOT running"
    echo "   → Run: docker-compose -f docker-compose.yolov11.yml up -d mongo"
    exit 1
fi

echo ""
echo "2. Checking network connectivity..."
MONGO_IP=$(docker inspect yolov11-mongo -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
APP_IP=$(docker inspect yolov11-cpu -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

echo "   MongoDB IP: $MONGO_IP"
echo "   App IP: $APP_IP"

if [ -z "$MONGO_IP" ]; then
    echo "   ❌ MongoDB has no IP address (network issue)"
    exit 1
fi

echo ""
echo "3. Testing hostname resolution from app container..."
if docker exec yolov11-cpu getent hosts mongo > /dev/null 2>&1; then
    echo "   ✅ Hostname 'mongo' resolves correctly"
elif docker exec yolov11-cpu python3 -c "import socket; socket.gethostbyname('mongo')" > /dev/null 2>&1; then
    echo "   ✅ Hostname 'mongo' resolves via Python"
else
    echo "   ❌ Cannot resolve hostname 'mongo'"
    echo "   → Containers may be on different networks"
    exit 1
fi

echo ""
echo "4. Testing MongoDB connection..."
if docker exec yolov11-cpu python3 -c "from pymongo import MongoClient; MongoClient('mongodb://mongo:27017', serverSelectionTimeoutMS=5000).server_info()" > /dev/null 2>&1; then
    echo "   ✅ MongoDB connection successful"
else
    echo "   ❌ Cannot connect to MongoDB"
    echo "   → MongoDB may not be accepting connections yet"
    exit 1
fi

echo ""
echo "✅ All checks passed! MongoDB is accessible."
```

Save this as `check_mongo.sh` and run:
```bash
chmod +x check_mongo.sh
./check_mongo.sh
```

---

## 🛠️ Alternative: Use IP Address Instead of Hostname

If hostname resolution continues to fail, modify the connection string:

### Option 1: Get MongoDB IP and Use It

```bash
# Get MongoDB container IP
MONGO_IP=$(docker inspect yolov11-mongo -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
echo "MongoDB IP: $MONGO_IP"

# Update docker-compose.yolov11.yml
# Change: MONGO_URI=mongodb://mongo:27017
# To: MONGO_URI=mongodb://172.21.0.2:27017  (use actual IP)
```

### Option 2: Use Docker Host Network (Not Recommended)

Modify `docker-compose.yolov11.yml`:
```yaml
services:
  yolov11:
    network_mode: "host"  # Add this line
    # ... rest of config
```

---

## 📋 Checklist for Your Colleague

Ask them to verify:

- [ ] Is Docker Compose installed? (`docker-compose --version`)
- [ ] Are they in the correct directory? (`pwd` should show `.../yolov11`)
- [ ] Is the compose file correct? (`ls docker-compose.yolov11.yml`)
- [ ] Are both containers running? (`docker ps`)
- [ ] Are they on the same network? (Check with `docker network inspect yolov11_default`)
- [ ] Can they ping MongoDB? (`docker exec yolov11-cpu ping mongo`)
- [ ] Is MongoDB ready? (`docker logs yolov11-mongo | grep "Waiting for connections"`)

---

## 🚨 Common Mistakes

### 1. Starting Containers Separately
❌ **Wrong:**
```bash
docker run yolov11-cpu ...
docker run yolov11-mongo ...
```

✅ **Correct:**
```bash
docker-compose -f docker-compose.yolov11.yml up -d
```

### 2. Using Wrong Compose File
❌ **Wrong:**
```bash
docker-compose up -d  # Uses docker-compose.yml
```

✅ **Correct:**
```bash
docker-compose -f docker-compose.yolov11.yml up -d
```

### 3. Containers on Different Networks
This happens when containers are started at different times or with different methods.

**Solution:**
```bash
# Always start together
docker-compose -f docker-compose.yolov11.yml down
docker-compose -f docker-compose.yolov11.yml up -d
```

---

## 📞 If Still Not Working

### Collect Diagnostic Information:

```bash
# Save all diagnostics to a file
{
    echo "=== Docker Version ==="
    docker --version
    docker-compose --version
    
    echo -e "\n=== Running Containers ==="
    docker ps -a
    
    echo -e "\n=== Networks ==="
    docker network ls
    docker network inspect yolov11_default 2>/dev/null || echo "Network not found"
    
    echo -e "\n=== MongoDB Logs ==="
    docker logs yolov11-mongo --tail 50
    
    echo -e "\n=== App Logs ==="
    docker logs yolov11-cpu --tail 50
    
    echo -e "\n=== Network Test ==="
    docker exec yolov11-cpu python3 -c "import socket; print('Resolving mongo:', socket.gethostbyname('mongo'))" 2>&1
} > diagnostics.txt

cat diagnostics.txt
```

Send the `diagnostics.txt` file for further analysis.

---

## ✅ Working Configuration

Once fixed, verify everything works:

```bash
# 1. Start services
docker-compose -f docker-compose.yolov11.yml up -d

# 2. Wait for startup
sleep 10

# 3. Test MongoDB connection
docker exec yolov11-cpu python3 -c "
from src.core.storage.mongo import get_mongo_db
db = get_mongo_db()
print('✅ MongoDB connected!')
print('Collections:', db.list_collection_names())
"

# 4. Test API
curl http://localhost:8000/health

# 5. Access dashboard
echo "Dashboard: http://localhost:8501"
```

---

**Status**: Follow these steps in order and the issue should be resolved! 🎯


