# 🔧 MongoDB "No IP Address" Fix Guide

## Problem
Your `check_mongo.sh` script shows:
- ✅ MongoDB container is running
- ❌ MongoDB IP: NOT FOUND
- ❌ Cannot resolve hostname 'mongo'

This indicates the MongoDB container is **not actually running** or is **crashing immediately** after start.

---

## Quick Fix (Recommended)

### Option 1: Automated Fix Script
```bash
cd ~/proj/yolov11GT  # or wherever your project is
./fix_mongo_no_ip.sh
```

This interactive script will:
1. Capture MongoDB logs for diagnosis
2. Check if port 27017 is already in use
3. Optionally remove corrupted `mongo_data` directory
4. Perform complete Docker cleanup
5. Restart containers with monitoring
6. Verify MongoDB gets an IP address

---

### Option 2: Manual Quick Fix

If the automated script doesn't work, try this manual fix:

```bash
cd ~/proj/yolov11GT

# Step 1: Check MongoDB logs
docker logs yolov11-mongo --tail 50

# Step 2: Stop everything
docker-compose -f docker-compose.yolov11.yml down

# Step 3: Remove potentially corrupted data (⚠️ deletes all MongoDB data!)
rm -rf ./mongo_data

# Step 4: Clean Docker networks
docker network prune -f

# Step 5: Restart
docker-compose -f docker-compose.yolov11.yml up -d

# Step 6: Wait for MongoDB to initialize
sleep 15

# Step 7: Verify MongoDB has an IP now
docker inspect yolov11-mongo -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
# Should print something like: 172.18.0.2

# Step 8: Run the diagnostic again
./check_mongo.sh
```

---

## Common Root Causes

### 1. Port 27017 Already in Use
**Check:**
```bash
sudo lsof -i :27017
```

**Fix:**
If you see another process using port 27017:
```bash
# Option A: Kill the other process
sudo kill -9 <PID>

# Option B: Change the port in docker-compose.yolov11.yml
# Edit the mongo service:
#   ports:
#     - "27018:27017"  # Use 27018 instead
# Then also update MONGO_URI in yolov11 service:
#   - MONGO_URI=mongodb://mongo:27017  # Keep as 27017 (internal port)
```

---

### 2. Corrupted MongoDB Data
The `mongo_data` directory can become corrupted if:
- Docker was force-stopped during MongoDB write
- Disk space ran out
- System crashed

**Fix:**
```bash
docker-compose -f docker-compose.yolov11.yml down
rm -rf ./mongo_data  # ⚠️ DELETES ALL DATA
docker-compose -f docker-compose.yolov11.yml up -d
```

---

### 3. Insufficient Disk Space
**Check:**
```bash
df -h
```

**Fix:**
- Free up at least 1GB of disk space
- Remove old Docker images: `docker image prune -a`
- Remove old containers: `docker container prune`

---

### 4. Docker Networking Bug
Sometimes Docker's internal DNS gets corrupted.

**Fix:**
```bash
# Restart Docker daemon
sudo systemctl restart docker

# OR on systems without systemd:
sudo service docker restart

# Then restart containers
docker-compose -f docker-compose.yolov11.yml down
docker network prune -f
docker-compose -f docker-compose.yolov11.yml up -d
```

---

## Verification Steps

After applying any fix, verify MongoDB is working:

```bash
# 1. Check MongoDB container has an IP
docker inspect yolov11-mongo -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
# Should output: 172.18.0.X (some IP)

# 2. Check MongoDB is listening on port 27017
docker exec yolov11-mongo mongosh --eval "db.adminCommand('ping')"
# Should output: { ok: 1 }

# 3. Test connection from app container
docker exec yolov11-cpu python3 -c "
from pymongo import MongoClient
client = MongoClient('mongodb://mongo:27017', serverSelectionTimeoutMS=5000)
print('✅ Connected to MongoDB version:', client.server_info()['version'])
"

# 4. Run full diagnostics
./check_mongo.sh
```

---

## Still Not Working?

If MongoDB still has no IP after trying all the above:

### 1. Check MongoDB Container Logs
```bash
docker logs yolov11-mongo --tail 100 > /tmp/mongo_full_logs.txt
cat /tmp/mongo_full_logs.txt
```

Look for specific error messages and search online for solutions.

### 2. Test MongoDB in Isolation
```bash
# Stop all project containers
docker-compose -f docker-compose.yolov11.yml down

# Start just MongoDB without docker-compose
docker run -d --name test-mongo -p 27017:27017 mongo:6

# Check if it gets an IP
docker inspect test-mongo -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'

# If this works, the problem is with docker-compose configuration
# If this doesn't work, the problem is with Docker or the system
```

### 3. Check Docker Version
```bash
docker --version
docker-compose --version
```

Recommended versions:
- Docker: 20.10+ or 24.0+
- Docker Compose: 1.29+ or 2.0+

### 4. Check Docker Daemon Status
```bash
sudo systemctl status docker
# Should be: active (running)

# If not running:
sudo systemctl start docker
```

---

## Prevention

To avoid this issue in the future:

1. **Always use `./run_services.sh` to start/stop** - it handles cleanup properly
2. **Don't force-kill Docker containers** - use `docker-compose down` gracefully
3. **Monitor disk space** - keep at least 5GB free
4. **Regular cleanup**:
   ```bash
   # Weekly cleanup
   docker system prune -f
   docker volume prune -f
   ```

---

## Contact Information

If you've tried everything and MongoDB still has no IP:

1. Share the output of:
   - `docker logs yolov11-mongo --tail 100`
   - `docker version`
   - `docker-compose version`
   - `df -h`
   - `sudo lsof -i :27017`

2. Check if there are any firewall rules blocking Docker networking:
   ```bash
   sudo iptables -L
   ```

3. Consider reinstalling Docker (last resort):
   ```bash
   # Ubuntu/Debian
   sudo apt-get remove docker docker-engine docker.io containerd runc
   sudo apt-get update
   sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
   ```


