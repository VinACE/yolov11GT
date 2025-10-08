# ReID Accuracy Tuning Guide

**Problem**: Getting 13 unique visitors instead of 11 (ground truth)  
**Issue**: Over-counting by 2 visitors - ReID matching is too strict  
**Goal**: Improve matching so same person isn't counted multiple times

---

## Current Configuration Analysis

### Your Current Settings (docker-compose.yolov11.yml)

```yaml
REID_SIM_THRESHOLD=0.65          # ⚠️ TOO STRICT
FRAME_PROCESS_EVERY=30           # ⚠️ TOO FAST (skipping 29 frames)
REID_RERANK_ALPHA=0.40
REID_RERANK_MARGIN=0.04
FEATURE_AVG_WINDOW=8
REID_TOPK=5
```

### What's Happening

**Problem 1: Threshold Too High (0.65)**
- Threshold of 0.65 means two people need 65% similarity to be considered same person
- If same person looks slightly different (angle, lighting, pose), they get counted as NEW visitor
- This causes **UNDER-matching** = Over-counting

**Problem 2: Processing Too Fast (Every 30th frame)**
- At 30 FPS, you're only processing 1 frame per second
- Missing 29 frames means losing track continuity
- Person might move significantly between processed frames
- Track IDs get lost and reassigned as new visitors

---

## Solution: Recommended Settings

### Option 1: More Matching (Recommended for your case)

```yaml
# ReID Matching - LOOSER for better matching
REID_SIM_THRESHOLD=0.55          # ⬇️ LOWER = more matching (was 0.65)
REID_RERANK_ALPHA=0.35           # ⬇️ Lower weight on EMA
REID_RERANK_MARGIN=0.03          # ⬇️ Smaller margin requirement
FEATURE_AVG_WINDOW=12            # ⬆️ More frames for stable embeddings

# Frame Processing - SLOWER for better tracking
FRAME_PROCESS_EVERY=15           # ⬇️ Process every 15th frame (was 30)
                                 # At 30 FPS: 2 frames/sec instead of 1
```

**Expected Result**: Reduce false new visitors, get closer to 11

### Option 2: Even More Aggressive Matching

```yaml
# If Option 1 still over-counts, try this:
REID_SIM_THRESHOLD=0.50          # ⬇️ Very loose matching
REID_RERANK_ALPHA=0.30
REID_RERANK_MARGIN=0.02
FEATURE_AVG_WINDOW=15            # ⬆️ More averaging

FRAME_PROCESS_EVERY=10           # ⬇️ Process every 10th frame (3 fps)
```

### Option 3: Maximum Accuracy (Slower but best results)

```yaml
# For production/offline processing where accuracy > speed
REID_SIM_THRESHOLD=0.48
REID_RERANK_ALPHA=0.25
REID_RERANK_MARGIN=0.02
FEATURE_AVG_WINDOW=20

FRAME_PROCESS_EVERY=5            # ⬇️ Process every 5th frame (6 fps)
MIN_CROP_HEIGHT=120              # ⬆️ Better quality crops
```

---

## How the Matching Works

### Code Flow (from multicam.py)

```python
# 1. Get top-k candidates from FAISS
candidates = self.reid_index.search_topk(embedding, topk=5)

# 2. Rerank against EMA (exponential moving average)
for each candidate:
    score = alpha * ema_similarity + (1-alpha) * raw_similarity
    
# 3. Check if top candidate passes thresholds:
if (top_similarity >= REID_SIM_THRESHOLD    # Similarity threshold
    AND (top_score - second_score) >= REID_RERANK_MARGIN    # Margin
    AND not_used_this_frame):                # Uniqueness
    → MATCH! (same person)
else:
    → NEW VISITOR (different person)
```

### What Each Parameter Does

| Parameter | Effect | Lower Value | Higher Value |
|-----------|--------|-------------|--------------|
| `REID_SIM_THRESHOLD` | Matching strictness | More matching ⬇️ | Less matching ⬆️ |
| `FRAME_PROCESS_EVERY` | Processing speed | Slower, better tracking | Faster, may lose tracks |
| `REID_RERANK_ALPHA` | EMA weight | Less history influence | More history influence |
| `REID_RERANK_MARGIN` | Match confidence | Easier to match | Harder to match |
| `FEATURE_AVG_WINDOW` | Embedding stability | Less averaging | More averaging |
| `MIN_CROP_HEIGHT` | Crop quality | Accept smaller crops | Require larger crops |

---

## Step-by-Step Tuning Process

### Step 1: Start with Recommended Settings

Edit `docker-compose.yolov11.yml`:

```yaml
environment:
  # ... other settings ...
  - REID_SIM_THRESHOLD=0.55      # ← Change from 0.65
  - FRAME_PROCESS_EVERY=15       # ← Change from 30
  - REID_RERANK_MARGIN=0.03      # ← Change from 0.04
  - FEATURE_AVG_WINDOW=12        # ← Change from 8
```

Restart:
```bash
docker-compose -f docker-compose.yolov11.yml restart yolov11
```

### Step 2: Test and Count

Run your test:
```bash
# Your testing process here
# Count unique visitors
```

### Step 3: Iterate

| Current Count | Ground Truth | Action |
|---------------|--------------|--------|
| 13 | 11 | **Over-counting** → Lower threshold (0.50-0.55) |
| 11 | 11 | **Perfect!** → Keep settings |
| 9 | 11 | **Under-counting** → Raise threshold (0.60-0.65) |

### Step 4: Fine-Tune

If still not perfect after threshold adjustment:

**Still over-counting?**
```yaml
REID_SIM_THRESHOLD=0.50          # Lower more
REID_RERANK_MARGIN=0.02          # Reduce margin
FRAME_PROCESS_EVERY=10           # Process more frames
```

**Now under-counting?**
```yaml
REID_SIM_THRESHOLD=0.58          # Raise slightly
REID_RERANK_MARGIN=0.04          # Increase margin
```

---

## Understanding Frame Processing Speed

### Current: FRAME_PROCESS_EVERY=30

```
30 FPS video:
[Frame 1] ← Process
[Frame 2-30] ← SKIP
[Frame 31] ← Process
[Frame 32-60] ← SKIP
...

Result: 1 frame per second processed
```

**Problem**: Person moves significantly between frame 1 and frame 31
- Track ID may be lost
- New detection might not match previous one
- Counted as new visitor

### Recommended: FRAME_PROCESS_EVERY=15

```
30 FPS video:
[Frame 1] ← Process
[Frame 2-15] ← SKIP
[Frame 16] ← Process
[Frame 17-30] ← SKIP
...

Result: 2 frames per second processed
```

**Benefit**: More continuity, better track association

### Aggressive: FRAME_PROCESS_EVERY=10

```
Result: 3 frames per second processed
Better tracking, slightly slower
```

---

## Trade-offs

### Accuracy vs Speed

| Setting | FPS | Accuracy | CPU Load |
|---------|-----|----------|----------|
| `FRAME_PROCESS_EVERY=30` | 1 fps | Low ❌ | Very Low |
| `FRAME_PROCESS_EVERY=15` | 2 fps | Medium ✓ | Low |
| `FRAME_PROCESS_EVERY=10` | 3 fps | Good ✓✓ | Medium |
| `FRAME_PROCESS_EVERY=5` | 6 fps | Excellent ✓✓✓ | High |
| `FRAME_PROCESS_EVERY=1` | 30 fps | Perfect ✓✓✓✓ | Very High |

### Matching Threshold Impact

| Threshold | Effect | Risk |
|-----------|--------|------|
| **0.70+** | Very strict | **Over-counting** (same person = 2 visitors) |
| **0.60-0.65** | Balanced | Good for most cases |
| **0.50-0.55** | Loose | Better matching, slight risk of merging |
| **0.40-0.45** | Very loose | **Under-counting** (2 people = 1 visitor) |

---

## Diagnostic Commands

### Check Current Unique Count

```bash
docker exec yolov11-cpu python3 -c "
import sys; sys.path.insert(0, '/app/src')
from core.storage.mongo import get_mongo_db
db = get_mongo_db()
unique = len(db.visit_events.distinct('global_id'))
print(f'Current unique visitors: {unique}')
print(f'Ground truth: 11')
print(f'Difference: {unique - 11}')
"
```

### View ReID Assignment Logs

```bash
# Check debug logs to see matching decisions
docker exec yolov11-cpu cat /app/debug/reid_assignment_log.jsonl | tail -20
```

### Analyze Global IDs

```bash
docker exec yolov11-cpu python3 -c "
import sys; sys.path.insert(0, '/app/src')
from core.storage.mongo import get_mongo_db
db = get_mongo_db()
gids = db.visit_events.distinct('global_id')
print(f'Total unique global_ids: {len(gids)}')
print('Global IDs:')
for i, gid in enumerate(sorted(gids), 1):
    print(f'  {i}. {gid}')
"
```

---

## Recommended Tuning Workflow

### Phase 1: Threshold Tuning (Quick)

1. Start with `REID_SIM_THRESHOLD=0.55`
2. Test and count
3. Adjust in steps of 0.05:
   - Over-counting? → Lower to 0.50
   - Under-counting? → Raise to 0.60
4. Repeat until count matches ground truth

### Phase 2: Frame Processing (If needed)

1. If threshold tuning gets close but not perfect:
   - Try `FRAME_PROCESS_EVERY=15` (from 30)
2. Test again
3. If still not perfect:
   - Try `FRAME_PROCESS_EVERY=10`

### Phase 3: Fine-Tuning (Optional)

Once count is correct, optimize for:
- **Speed**: Increase `FRAME_PROCESS_EVERY` while maintaining accuracy
- **Stability**: Increase `FEATURE_AVG_WINDOW` for smoother embeddings
- **Quality**: Increase `MIN_CROP_HEIGHT` for better crops

---

## Quick Fix for Your Case

Based on your issue (13 instead of 11), try this first:

```bash
# Edit docker-compose.yolov11.yml and change:
REID_SIM_THRESHOLD=0.55     # From 0.65
FRAME_PROCESS_EVERY=15      # From 30

# Then restart:
docker-compose -f docker-compose.yolov11.yml restart yolov11
```

**Expected outcome**: Should reduce count from 13 → 11 or 12

---

## Advanced: Understanding the Math

### Cosine Similarity

```python
similarity = dot(embedding1, embedding2) / (norm(emb1) * norm(emb2))
# Range: -1.0 to 1.0 (higher = more similar)
```

### Reranking Score

```python
score = alpha * ema_similarity + (1 - alpha) * raw_similarity
# alpha = 0.40 means 40% weight on history, 60% on current
```

### Matching Decision

```python
is_match = (
    similarity >= threshold           # Pass minimum similarity
    AND (top_score - second_score) >= margin  # Clear winner
    AND not_already_used              # One person per frame
)
```

---

## Summary

**Your Issue**: Over-counting (13 vs 11) = ReID matching too strict

**Root Causes**:
1. Threshold too high (0.65) → Same person counted as different visitors
2. Frame processing too fast (30) → Losing track continuity

**Solution**:
```yaml
REID_SIM_THRESHOLD=0.55  # Lower = more matching
FRAME_PROCESS_EVERY=15   # Slower = better tracking
```

**Next Steps**:
1. Apply recommended settings
2. Restart container
3. Test and count
4. Iterate until count = 11

Good luck! 🎯

