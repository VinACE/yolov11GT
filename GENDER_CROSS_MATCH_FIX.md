# Critical Bug: Male and Female Getting Same Global ID

**Date**: October 9, 2025  
**Severity**: 🔴 CRITICAL  
**Issue**: Same global ID assigned to different genders (male and female)

---

## 🔍 Problem Found

### Example from your data:
```
✅ G1759994288_cam2_5: gender=male
✅ G1759994288_cam2_6: gender=female
```

**Same global ID prefix `G1759994288_` for BOTH male AND female!**

### Analysis:
- ReID logs show **`similarity_score: 1.0`** (perfect 100% match)
- This is **impossible** for different people
- Suggests embeddings are identical or very similar

---

## 🐛 Root Causes

### 1. **Using Stub/Random Embedder** (Most Likely)

If you're still using the stub embedder (not Hybrid or OSNet):
- Stub embedder generates embeddings based on crop SIZE
- Similar-sized people → similar embeddings → matched as same person!
- Gender filtering can't help if embeddings are already wrong

**Check**:
```bash
docker-compose -f docker-compose.yolov11.yml logs yolov11 | grep "Using.*ReID"
```

**Should see**:
```
✅ Using Hybrid ReID (FaceNet + OSNet)
# OR
✅ Using OSNet production ReID
```

**If you see**:
```
⚠️  Using stub ReID embedder
```
→ **THIS IS THE PROBLEM!**

---

### 2. **Gender Filtering Not Applied**

Even with good embeddings, if gender filtering fails:
- Male and female CAN match if gender detection returns 'unknown'
- Current logic allows 'unknown' to match with anyone

**Code location**: `src/core/reid/embedding.py` lines 114-121

---

### 3. **Gender Classification Returns 'Unknown'**

If gender classifier fails:
- Low confidence → returns 'unknown'
- Poor image quality → returns 'unknown'
- 'Unknown' can match with any gender

---

## ✅ Solution: 3-Step Fix

### Step 1: Ensure Real ReID Model is Used

**Check current configuration**:
```bash
docker exec yolov11-cpu printenv | grep -E "USE_HYBRID|FASTREID_ENABLED"
```

**Should show**:
```
USE_HYBRID_REID=1      # Best option
# OR
FASTREID_ENABLED=1     # Accurate but slow
```

**If both are 0**:
- You're using stub embedder → FIX THIS FIRST!

**Fix**:
1. Already enabled in your `docker-compose.yolov11.yml`
2. But you need to RESTART the pipeline!

```bash
# Stop current pipeline
docker exec yolov11-cpu pkill -f run_pipeline

# Restart services with new config
./run_services.sh
# Choose option 6 (Start All Services)
```

---

### Step 2: Increase ReID Threshold (Reduce False Matches)

Your current threshold might be too low:

```yaml
# docker-compose.yolov11.yml
REID_SIM_THRESHOLD=0.6435   # Current

# Try increasing:
REID_SIM_THRESHOLD=0.70     # Stricter (fewer false matches)
```

**Effect**:
- Higher threshold = stricter matching
- Reduces chance of different people matching
- May create more unique IDs (acceptable trade-off)

**Edit**:
```bash
nano docker-compose.yolov11.yml
# Find REID_SIM_THRESHOLD
# Change 0.6435 → 0.70
```

**Restart**:
```bash
docker-compose -f docker-compose.yolov11.yml restart yolov11
```

---

### Step 3: Improve Gender Classification Confidence

**Check current gender detections**:
```bash
docker exec yolov11-cpu python3 -c "
import sys
sys.path.insert(0, '/app/src')
from core.storage.mongo import get_mongo_db

db = get_mongo_db()
visitors = list(db.visitors.find())

print(f'Total visitors: {len(visitors)}')
print('')
for v in visitors:
    gid = v.get('global_id', 'NO_ID')
    gender = v.get('gender', 'NOT_SET')
    print(f'{gid}: {gender}')
"
```

**If you see many 'unknown'**:
- Gender classifier confidence too high (0.6)
- Lower it to detect more genders

```yaml
# docker-compose.yolov11.yml
# Add this env var:
- GENDER_CONFIDENCE_THRESHOLD=0.5   # Default is 0.6, lower = more detections
```

---

## 🔧 Immediate Fix (Quick)

**Do this NOW**:

```bash
# 1. Stop current pipeline
docker exec yolov11-cpu pkill -f run_pipeline || true

# 2. Clear database for clean test
docker exec -i yolov11-mongo mongosh --quiet --eval "db.getSiblingDB('yolov11').dropDatabase()"

# 3. Increase threshold to prevent false matches
# Edit docker-compose.yolov11.yml:
# REID_SIM_THRESHOLD=0.70

# 4. Restart services
docker-compose -f docker-compose.yolov11.yml restart yolov11

# 5. Start pipeline again
./run_services.sh
# Choose option 3 or 6
```

---

## 🧪 How to Verify Fix

### Test 1: Check Embedder

```bash
docker-compose -f docker-compose.yolov11.yml logs yolov11 | grep -i "using.*reid"
```

**Should see**:
```
✅ Using Hybrid ReID (FaceNet + OSNet)
```

**NOT**:
```
⚠️  Using stub ReID embedder   ← BAD!
```

---

### Test 2: Check Gender Filtering

Run pipeline, then check:

```bash
docker exec yolov11-cpu python3 -c "
import sys
sys.path.insert(0, '/app/src')
from core.storage.mongo import get_mongo_db
from collections import defaultdict

db = get_mongo_db()
visitors = list(db.visitors.find())

# Group by global_id
by_gid = defaultdict(list)
for v in visitors:
    gid = v.get('global_id', 'NO_ID')
    by_gid[gid].append(v.get('gender', 'unknown'))

# Check for cross-gender matches
print('Checking for cross-gender matches...')
print('')
found_issue = False
for gid, genders in by_gid.items():
    unique_genders = set(g for g in genders if g != 'unknown')
    if len(unique_genders) > 1:
        print(f'❌ CROSS-GENDER MATCH: {gid}')
        print(f'   Genders: {genders}')
        found_issue = True

if not found_issue:
    print('✅ No cross-gender matches found!')
"
```

---

### Test 3: Check Similarity Scores

```bash
docker exec yolov11-cpu tail -20 /app/outputs/debug/reid_assignment_log.jsonl | grep -o '"similarity_score": [0-9.]*' | sort -u
```

**Should see varied scores**:
```
"similarity_score": 0.65
"similarity_score": 0.73
"similarity_score": 0.81
"similarity_score": 0.95
```

**NOT all 1.0**:
```
"similarity_score": 1.0    ← Suspicious if ALL matches are 1.0!
```

---

## 📊 Expected Results After Fix

### Before (Broken):
```
G1759994288_cam2_5: gender=male    ← Same ID prefix!
G1759994288_cam2_6: gender=female  ← Same ID prefix!
Similarity: 1.0 (perfect match - wrong!)
```

### After (Fixed):
```
G1759994288_cam2_5: gender=male
G1759994310_cam2_6: gender=female   ← Different ID!
Similarity: 0.73 (realistic score)
```

---

## 🎯 Root Cause Summary

| Issue | Cause | Fix |
|-------|-------|-----|
| **Same embeddings** | Using stub embedder | Enable Hybrid/OSNet |
| **1.0 similarity** | Stub uses crop size | Use real ReID model |
| **Cross-gender match** | Threshold too low | Increase to 0.70 |
| **Gender = unknown** | Confidence too high | Lower to 0.5 |

---

## 🚀 Action Plan

### Priority 1: Use Real ReID Model (CRITICAL)

```bash
# Check if Hybrid is enabled
docker exec yolov11-cpu printenv USE_HYBRID_REID
# Should show: 1

# If not, it's in docker-compose.yolov11.yml but pipeline needs restart!
./run_services.sh
# Choose option 6 (restarts everything)
```

### Priority 2: Increase Threshold

```yaml
# docker-compose.yolov11.yml
REID_SIM_THRESHOLD=0.70   # Increase from 0.6435
```

### Priority 3: Test and Verify

```bash
# Clear database
docker exec -i yolov11-mongo mongosh --quiet --eval "db.getSiblingDB('yolov11').dropDatabase()"

# Run pipeline
# Check for cross-gender matches (see Test 2 above)
```

---

## 💡 Why This Happened

**Most likely**:
1. You configured Hybrid ReID in `docker-compose.yolov11.yml` ✅
2. But the pipeline was already running with the OLD stub embedder ❌
3. Stub embedder uses crop size → similar crops = 1.0 similarity ❌
4. Male and female with similar body size → matched as same person ❌

**Solution**: Just RESTART the pipeline with the new configuration!

---

## 🆘 Still Having Issues?

### Check which embedder is ACTUALLY being used:

Create test file:
```python
# test_embedder.py
import sys
sys.path.insert(0, '/app/src')
from core.pipeline.multicam import MultiCamPipeline
from core.config import CAMERA_SOURCES

pipeline = MultiCamPipeline(camera_sources=CAMERA_SOURCES, use_osnet=True)
print(f"Embedder: {type(pipeline.embedder).__name__}")
print(f"Dimension: {pipeline.embedder.dim}")
```

Run:
```bash
docker exec yolov11-cpu python3 /app/test_embedder.py
```

**Should show**:
```
Embedder: HybridEmbedder
Dimension: 512
```

**NOT**:
```
Embedder: ReidEmbedder     ← This is the stub! Fix needed!
Dimension: 256
```

---

## 📝 Summary

**Problem**: Male and female getting same global ID  
**Root Cause**: Stub embedder (random features based on crop size)  
**Solution**: Enable Hybrid/OSNet ReID and restart pipeline  
**Prevention**: Increase threshold to 0.70  

**Status**: ✅ Fix available, needs pipeline restart

---

**Next Step**: Restart your pipeline with `./run_services.sh` option 6!

