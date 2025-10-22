#!/bin/bash
# Test FastReID accuracy after enabling it
# Run this after restarting the service with FastReID enabled

set -e

echo "=========================================="
echo "FastReID Accuracy Test"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if service is running
echo "📡 Checking if service is running..."
if ! docker ps | grep -q "yolov11-cpu"; then
    echo -e "${RED}❌ yolov11-cpu container is not running${NC}"
    echo "Start with: docker-compose -f docker-compose.yolov11.yml up -d"
    exit 1
fi
echo -e "${GREEN}✅ Service is running${NC}"
echo ""

# Check which model is loaded
echo "🔍 Checking which ReID model is loaded..."
MODEL_LOG=$(docker-compose -f docker-compose.yolov11.yml logs yolov11 2>/dev/null | grep -E "OSNet|FastReID" | tail -1)

if echo "$MODEL_LOG" | grep -q "FastReID"; then
    echo -e "${GREEN}✅ FastReID is loaded${NC}"
    echo "   $MODEL_LOG"
elif echo "$MODEL_LOG" | grep -q "OSNet"; then
    echo -e "${YELLOW}⚠️  OSNet is loaded (should be FastReID)${NC}"
    echo "   $MODEL_LOG"
    echo ""
    echo "To enable FastReID:"
    echo "1. Edit docker-compose.yolov11.yml"
    echo "2. Set FASTREID_ENABLED=1"
    echo "3. Set REID_SIM_THRESHOLD=0.42"
    echo "4. Restart: docker-compose -f docker-compose.yolov11.yml restart yolov11"
    exit 1
else
    echo -e "${RED}❌ Could not determine which model is loaded${NC}"
    echo "Check logs: docker-compose -f docker-compose.yolov11.yml logs yolov11 | grep -i reid"
fi
echo ""

# Check threshold
echo "🎯 Checking ReID threshold..."
THRESHOLD=$(docker exec yolov11-cpu printenv | grep REID_SIM_THRESHOLD | cut -d= -f2)
echo "   Current threshold: $THRESHOLD"

if (( $(echo "$THRESHOLD < 0.50" | bc -l) )); then
    echo -e "${GREEN}✅ Threshold is in FastReID range (0.40-0.45 optimal)${NC}"
elif (( $(echo "$THRESHOLD > 0.60" | bc -l) )); then
    echo -e "${YELLOW}⚠️  Threshold seems high for FastReID (try 0.42)${NC}"
else
    echo -e "${YELLOW}⚠️  Threshold is in transition range${NC}"
fi
echo ""

# Check if FastReID model files exist
echo "📦 Checking FastReID model files..."
if docker exec yolov11-cpu test -f /app/models/fast-reid-weights/msmt17/msmt_bot_R50.pth 2>/dev/null || \
   docker exec yolov11-cpu test -f /app/models/fast-reid-weights/msmt17/bagtricks_R50.pth 2>/dev/null; then
    echo -e "${GREEN}✅ FastReID weights found${NC}"
else
    echo -e "${RED}❌ FastReID weights not found${NC}"
    echo "Download models from: https://github.com/JDAI-CV/fast-reid"
    exit 1
fi
echo ""

# Check current visitor count
echo "👥 Current unique visitor count..."
UNIQUE_COUNT=$(docker exec yolov11-cpu python3 -c "
import sys
sys.path.insert(0, '/app/src')
from core.storage.mongo import get_mongo_db
db = get_mongo_db()
try:
    unique = len(db.visit_events.distinct('global_id', {'global_id': {'$ne': None}}))
    print(unique)
except Exception as e:
    print('0')
" 2>/dev/null)

echo "   Detected: $UNIQUE_COUNT people"
echo "   Expected: 11 people (ground truth)"

if [ "$UNIQUE_COUNT" -eq 11 ]; then
    echo -e "${GREEN}✅ PERFECT! Accuracy: 100% (11/11)${NC}"
elif [ "$UNIQUE_COUNT" -ge 9 ] && [ "$UNIQUE_COUNT" -le 13 ]; then
    ACCURACY=$(echo "scale=1; $UNIQUE_COUNT / 11 * 100" | bc)
    echo -e "${YELLOW}⚠️  Close! Accuracy: ~$ACCURACY%${NC}"
    echo ""
    echo "Fine-tuning suggestions:"
    if [ "$UNIQUE_COUNT" -gt 11 ]; then
        echo "  • Too many people detected → Lower threshold to 0.40"
    else
        echo "  • Too few people detected → Raise threshold to 0.44"
    fi
elif [ "$UNIQUE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No visitors detected yet${NC}"
    echo "   Run your test video first"
else
    echo -e "${RED}❌ Accuracy needs improvement${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check if FastReID is actually being used"
    echo "  2. Try threshold range: 0.38 - 0.46"
    echo "  3. Check MIN_CROP_HEIGHT (should be 80-120)"
    echo "  4. Review logs: docker-compose -f docker-compose.yolov11.yml logs yolov11"
fi
echo ""

# Show recent ReID decisions
echo "📋 Recent ReID matching decisions..."
echo "(Showing last 5 matches)"
docker exec yolov11-cpu tail -5 /app/debug/reid_assignment_log.jsonl 2>/dev/null | \
    python3 -c "
import sys
import json
for line in sys.stdin:
    try:
        data = json.loads(line)
        sim = data.get('similarity', 0)
        gid = data.get('global_id', 'unknown')[:20]
        decision = 'MATCH' if sim > 0.42 else 'NEW'
        print(f'  {decision:5s} | sim={sim:.3f} | {gid}')
    except:
        pass
" || echo "   (No log file yet)"
echo ""

echo "=========================================="
echo "Test Complete!"
echo "=========================================="
echo ""

echo "Next steps:"
echo "1. If accuracy is 100%: ✅ You're done! Lock this config."
echo "2. If accuracy is 90-95%: Try fine-tuning threshold (±0.02)"
echo "3. If accuracy is <90%: Check troubleshooting in guide"
echo ""
echo "See detailed guide: REID_ACCURACY_IMPROVEMENT_GUIDE.md"

