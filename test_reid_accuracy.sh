#!/bin/bash
# ReID Accuracy Testing Script
# Tests different threshold settings and reports unique visitor counts

echo "=========================================="
echo "ReID Accuracy Testing"
echo "=========================================="
echo ""
echo "Ground Truth: 11 unique visitors"
echo "Current Count: $(docker exec yolov11-cpu python3 -c "import sys; sys.path.insert(0, '/app/src'); from core.storage.mongo import get_mongo_db; print(len(get_mongo_db().visit_events.distinct('global_id')))" 2>/dev/null || echo 'N/A')"
echo ""

# Function to test a specific configuration
test_config() {
    local threshold=$1
    local frame_every=$2
    local description=$3
    
    echo "=========================================="
    echo "Test: $description"
    echo "  REID_SIM_THRESHOLD=$threshold"
    echo "  FRAME_PROCESS_EVERY=$frame_every"
    echo "=========================================="
    
    # Note: To test, you need to:
    # 1. Update docker-compose.yolov11.yml with these values
    # 2. Restart container: docker-compose -f docker-compose.yolov11.yml restart yolov11
    # 3. Clear database: docker exec yolov11-cpu python3 -c "import sys; sys.path.insert(0, '/app/src'); from core.storage.mongo import get_mongo_db; db=get_mongo_db(); db.visit_events.delete_many({}); db.visitors.delete_many({})"
    # 4. Run your test video/cameras
    # 5. Count results
    
    echo ""
    echo "To apply this configuration:"
    echo "1. Edit docker-compose.yolov11.yml:"
    echo "   - REID_SIM_THRESHOLD=$threshold"
    echo "   - FRAME_PROCESS_EVERY=$frame_every"
    echo "2. Restart: docker-compose -f docker-compose.yolov11.yml restart yolov11"
    echo "3. Clear DB and retest"
    echo ""
}

# Current configuration
echo "=========================================="
echo "Current Configuration"
echo "=========================================="
docker exec yolov11-cpu env | grep -E "REID_SIM_THRESHOLD|FRAME_PROCESS_EVERY|REID_RERANK|FEATURE_AVG" | sort
echo ""

# Show current results
echo "=========================================="
echo "Current Database Analysis"
echo "=========================================="
docker exec yolov11-cpu python3 << 'ENDPY'
import sys
sys.path.insert(0, '/app/src')
from core.storage.mongo import get_mongo_db

db = get_mongo_db()
total = db.visit_events.count_documents({})
unique_vids = len(db.visit_events.distinct('visitor_id'))
unique_gids = len(db.visit_events.distinct('global_id'))

# Get unique person IDs from global_id
person_ids = set()
for gid in db.visit_events.distinct('global_id'):
    if gid and '_' in gid:
        person_id = gid.split('_')[-1]
        person_ids.add(person_id)

print(f"Total visit events: {total}")
print(f"Unique visitor_id: {unique_vids}")
print(f"Unique global_id: {unique_gids}")
print(f"Unique persons (from global_id): {len(person_ids)}")
print(f"")
print(f"Ground truth: 11")
print(f"Current result: {unique_gids}")
print(f"Difference: {unique_gids - 11:+d}")
print(f"")

if unique_gids > 11:
    print(f"⚠️  OVER-COUNTING by {unique_gids - 11}")
    print(f"   → Lower threshold (more matching)")
    print(f"   → Process more frames (lower FRAME_PROCESS_EVERY)")
elif unique_gids < 11:
    print(f"⚠️  UNDER-COUNTING by {11 - unique_gids}")
    print(f"   → Raise threshold (less matching)")
    print(f"   → Process fewer frames (higher FRAME_PROCESS_EVERY)")
else:
    print(f"✅ PERFECT MATCH!")
    print(f"   Current settings are optimal")
ENDPY

echo ""
echo "=========================================="
echo "Suggested Test Configurations"
echo "=========================================="
echo ""

# Test recommendations based on current count
current_count=$(docker exec yolov11-cpu python3 -c "import sys; sys.path.insert(0, '/app/src'); from core.storage.mongo import get_mongo_db; print(len(get_mongo_db().visit_events.distinct('global_id')))" 2>/dev/null || echo "0")

if [ "$current_count" -gt 11 ]; then
    echo "Current: Over-counting ($current_count vs 11)"
    echo ""
    test_config "0.55" "15" "Recommended: More Matching"
    test_config "0.50" "15" "Aggressive: Much More Matching"
    test_config "0.55" "10" "Alternative: Better Tracking"
elif [ "$current_count" -lt 11 ]; then
    echo "Current: Under-counting ($current_count vs 11)"
    echo ""
    test_config "0.60" "20" "Recommended: Less Matching"
    test_config "0.65" "25" "Conservative: Much Less Matching"
else
    echo "✅ Current count matches ground truth!"
    echo "   No changes needed"
fi

echo ""
echo "=========================================="
echo "Quick Test Workflow"
echo "=========================================="
echo ""
echo "1. Choose a configuration above"
echo "2. Edit docker-compose.yolov11.yml with the values"
echo "3. Restart container:"
echo "   docker-compose -f docker-compose.yolov11.yml restart yolov11"
echo "4. Clear database:"
echo "   docker exec yolov11-cpu python3 -c \"import sys; sys.path.insert(0, '/app/src'); from core.storage.mongo import get_mongo_db; db=get_mongo_db(); db.visit_events.delete_many({}); db.visitors.delete_many({})\""
echo "5. Run your test"
echo "6. Run this script again to check results"
echo ""

