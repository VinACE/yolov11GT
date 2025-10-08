# MongoDB 8 Upgrade Guide

## Summary
Successfully upgraded MongoDB from version 6 to version 8.

## What Changed
- **MongoDB Image**: `mongo:6` → `mongo:8`
- **MongoDB Version**: 6.x → **8.0.15**
- **Data Directory**: Old MongoDB 6 data backed up to `mongo_data.mongo6_backup/`

## Files Modified
- `docker-compose.yolov11.yml`: Updated `mongo` service to use `image: mongo:8`

## Upgrade Process

### 1. Update Docker Compose Configuration
```yaml
# docker-compose.yolov11.yml
mongo:
  image: mongo:8  # Changed from mongo:6
  container_name: yolov11-mongo
  restart: always
  ports:
    - "27017:27017"
  volumes:
    - ./mongo_data:/data/db
```

### 2. Stop Containers
```bash
docker-compose -f docker-compose.yolov11.yml down
```

### 3. Backup Old Data (Important!)
```bash
# MongoDB 6 data is incompatible with MongoDB 8
# Must start with fresh data directory
mv mongo_data mongo_data.mongo6_backup
```

### 4. Pull MongoDB 8 Image
```bash
docker pull mongo:8
```

### 5. Start Containers
```bash
docker-compose -f docker-compose.yolov11.yml up -d
```

### 6. Verify
```bash
# Check MongoDB version
docker exec yolov11-mongo mongosh --quiet --eval "db.version()"
# Output: 8.0.15

# Check containers
docker ps | grep mongo
# Should show: yolov11-mongo   mongo:8   Up X seconds

# Run diagnostics
./check_mongo.sh
# All checks should pass ✅
```

## Important Notes

### ⚠️ Data Incompatibility
MongoDB 8 **cannot read** MongoDB 6 data files directly. The database must be initialized with a fresh data directory.

**Before upgrade:**
- MongoDB 6 data is in `./mongo_data/`
- Backup is in `./mongo_data.mongo6_backup/`

**After upgrade:**
- MongoDB 8 starts with fresh `./mongo_data/`
- All previous data is lost (unless migrated)

### 🔄 Data Migration (If Needed)
If you need to migrate data from MongoDB 6 to MongoDB 8:

```bash
# Option 1: Export/Import (Recommended)
# 1. Start MongoDB 6 temporarily
docker run -d --name mongo6-temp -p 27018:27017 \
  -v $(pwd)/mongo_data.mongo6_backup:/data/db mongo:6

# 2. Export all databases
docker exec mongo6-temp mongodump --out=/tmp/mongo_backup

# 3. Stop MongoDB 6
docker stop mongo6-temp && docker rm mongo6-temp

# 4. Import to MongoDB 8
docker cp mongo6-temp:/tmp/mongo_backup ./mongo_backup
docker exec yolov11-mongo mongorestore /data/mongo_backup

# Option 2: Use mongodump/mongorestore manually
# See: https://www.mongodb.com/docs/manual/tutorial/backup-and-restore-tools/
```

For this project, we started fresh because:
- The system was in development/testing phase
- No production data to preserve
- Cleaner to start with fresh MongoDB 8 data

## Verification Checklist

- [x] MongoDB container running with `mongo:8` image
- [x] MongoDB version is 8.0.15
- [x] MongoDB has IP address (172.21.0.2)
- [x] Application can resolve `mongo` hostname
- [x] Python can connect via PyMongo
- [x] Database collections are accessible
- [x] `check_mongo.sh` passes all checks

## New Features in MongoDB 8

MongoDB 8.0 includes several improvements over 6.0:
- **Performance**: Improved query execution and index performance
- **Time Series**: Enhanced time-series collection capabilities
- **Aggregation**: New pipeline operators and optimizations
- **Security**: Updated encryption and authentication methods
- **Compatibility**: Maintains compatibility with existing PyMongo code

See: https://www.mongodb.com/docs/manual/release-notes/8.0/

## Rollback (If Needed)

To rollback to MongoDB 6:

```bash
# Stop containers
docker-compose -f docker-compose.yolov11.yml down

# Restore old data
rm -rf mongo_data
mv mongo_data.mongo6_backup mongo_data

# Change docker-compose.yolov11.yml back to:
# image: mongo:6

# Restart
docker-compose -f docker-compose.yolov11.yml up -d
```

## Status
✅ **MongoDB 8 upgrade completed successfully**
- Version: 8.0.15
- Status: Running and accessible
- Date: 2025-10-08


