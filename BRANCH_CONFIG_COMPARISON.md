# Branch Configuration Comparison

**Date**: October 8, 2025  
**Purpose**: Compare ReID and MongoDB configurations across branches

---

## Branch Overview

| Branch | MongoDB | Key Focus | Status |
|--------|---------|-----------|--------|
| **gtvin** | mongo:8 | Tuned OSNet + MongoDB 8 | ✅ Current, optimized |
| **gtdevvin** | mongo:6 | Older OSNet config | Legacy |
| **gtdev** | Unknown | OSNet initial | Development |
| **main** | Unknown | Base | Stable |

---

## Detailed Configuration Comparison

### MongoDB Configuration

| Setting | gtdevvin | gtvin (current) | Notes |
|---------|----------|-----------------|-------|
| **MongoDB Image** | mongo:6 | mongo:8 | ✅ Upgraded |
| **Null Filtering** | ❌ Not present | ✅ Present | Fixed for MongoDB 8 |

---

### ReID Configuration

| Parameter | gtdevvin | gtvin (current) | Impact |
|-----------|----------|-----------------|--------|
| **FRAME_PROCESS_EVERY** | 10 | 30 | gtvin 3x faster |
| **REID_SIM_THRESHOLD** | **0.71** | **0.6435** | gtdevvin much stricter |
| **FEATURE_AVG_WINDOW** | 5 | 11 | gtvin more stable |
| **MIN_CROP_HEIGHT** | 120 | 100 | gtvin more lenient |
| **REID_GALLERY_TTL** | 60s | 3600s | gtvin 60x longer |
| **SAME_CAM_CONTINUITY** | 10s | 12s | gtvin slightly longer |
| **REID_TOPK** | 5 | 6 | gtvin more candidates |
| **REID_EMA_MOMENTUM** | 0.9 | 0.88 | gtvin less sticky |
| **REID_RERANK_ALPHA** | ❌ Missing | 0.37 | gtvin has reranking |
| **REID_RERANK_MARGIN** | ❌ Missing | 0.032 | gtvin has margin check |
| **HANDOFF_WINDOW** | ❌ Missing | 10s | gtvin has cross-cam |
| **HANDOFF_MARGIN** | ❌ Missing | 0.04 | gtvin has handoff |

---

## Expected Results Analysis

### gtdevvin (REID_SIM_THRESHOLD=0.71)

Based on our extensive testing:
```
Threshold 0.71 would likely give:
  → 15-20 visitors (severe OVER-counting)
  → Same person counted multiple times
  → Too strict for matching
```

**Why?** From our testing:
- 0.65 → 13 visitors (over by 2)
- 0.71 would be even stricter → likely 15-20+

**Verdict**: ❌ gtdevvin threshold is TOO HIGH

---

### gtvin (REID_SIM_THRESHOLD=0.6435)

Based on our extensive testing:
```
Threshold 0.6435 gives:
  → 9 visitors (under-counting by 2)
  → OSNet's best achievable result
  → 82% accuracy
```

**Verdict**: ✅ gtvin threshold is OPTIMIZED (best OSNet can do)

---

## Frame Processing Comparison

### gtdevvin: FRAME_PROCESS_EVERY=10

```
At 30 FPS:
  → Processes 3 frames per second
  → Better track continuity
  → More CPU usage
  → Slower overall processing
```

**Testing showed**: Going from 30→24→15 improved count by ~1 visitor
- 10 would give even better tracking
- But much slower processing
- Diminishing returns

---

### gtvin: FRAME_PROCESS_EVERY=30

```
At 30 FPS:
  → Processes 1 frame per second  
  → Good enough for tracking
  → Lower CPU usage
  → Faster processing
```

**Verdict**: ✅ 30 is good balance for real-time

---

## MongoDB Version Impact

### gtdevvin: mongo:6
- ✅ Stable, proven
- ❌ Older version
- ⚠️ `distinct()` excludes null automatically (implicit behavior)

### gtvin: mongo:8
- ✅ Modern, better performance
- ✅ Latest features
- ⚠️ `distinct()` includes null (needs explicit filtering)
- ✅ Fixed with code changes

**Verdict**: ✅ mongo:8 is better (with fixes applied)

---

## Missing Parameters in gtdevvin

gtdevvin is **missing several important parameters** that we added:

| Parameter | Purpose | Impact of Missing |
|-----------|---------|-------------------|
| `REID_RERANK_ALPHA` | EMA reranking weight | No reranking = worse accuracy |
| `REID_RERANK_MARGIN` | Match confidence margin | No margin check = false matches |
| `HANDOFF_WINDOW_SECONDS` | Cross-camera handoff time | Poor cross-camera matching |
| `HANDOFF_MARGIN` | Cross-camera threshold relax | Misses cross-camera matches |
| `REID_EMA_MOMENTUM` | EMA update rate | Less adaptive embeddings |

These parameters improve matching accuracy significantly!

---

## Recommended Merge Strategy

### Option 1: Update gtdevvin with gtvin learnings ✅ RECOMMENDED

Apply gtvin's optimizations to gtdevvin:

```yaml
# Keep from gtdevvin (if you prefer):
FRAME_PROCESS_EVERY=10             # Better tracking (but slower)

# Update from gtvin (optimized):
REID_SIM_THRESHOLD=0.6435          # Much better than 0.71!
FEATURE_AVG_WINDOW=11              # More stable than 5
REID_GALLERY_TTL_SECONDS=3600      # Much longer than 60s
MIN_CROP_HEIGHT=100                # More lenient than 120

# Add missing from gtvin:
REID_RERANK_ALPHA=0.37
REID_RERANK_MARGIN=0.032
HANDOFF_WINDOW_SECONDS=10
HANDOFF_MARGIN=0.04
REID_EMA_MOMENTUM=0.88
REID_TOPK=6

# MongoDB:
image: mongo:8                      # Upgrade to MongoDB 8
```

**This would give you:**
- Better accuracy than current gtdevvin (0.71 is way too strict)
- Better tracking with frame=10
- All modern features
- MongoDB 8 benefits

---

### Option 2: Keep Both Branches Separate

- **gtvin**: Production (fast, frame=30, ~9 count)
- **gtdevvin**: High accuracy (slower, frame=10, need to tune threshold)

---

### Option 3: Merge to Single Branch

Combine best of both:
```yaml
# Best of both worlds
MongoDB: mongo:8                    # From gtvin
FRAME_PROCESS_EVERY: 20             # Middle ground (15-30)
REID_SIM_THRESHOLD: 0.6435          # From gtvin (optimized)
All other params: From gtvin        # Includes handoff, rerank, etc.
```

---

## Predicted Results by Configuration

### If You Test gtdevvin As-Is (threshold 0.71):

Based on our testing pattern:
```
Threshold  | Expected Result | Error
───────────────────────────────────────
0.71       | 15-20 visitors  | Over by 4-9
0.65       | 13 visitors     | Over by 2
0.6435     | 9 visitors      | Under by 2
```

**Prediction**: gtdevvin would give **15-20 visitors** (severe over-counting)

---

### Recommended gtdevvin Update:

Change these in gtdevvin branch:
```yaml
# Critical changes:
REID_SIM_THRESHOLD: 0.71 → 0.6435   # From our tuning
FEATURE_AVG_WINDOW: 5 → 11          # More stability
REID_GALLERY_TTL_SECONDS: 60 → 3600 # Don't forget visitors

# Add missing parameters:
- REID_RERANK_ALPHA=0.37
- REID_RERANK_MARGIN=0.032
- HANDOFF_WINDOW_SECONDS=10
- HANDOFF_MARGIN=0.04
- REID_EMA_MOMENTUM=0.88
- REID_TOPK=6

# Optional (better tracking but slower):
FRAME_PROCESS_EVERY: 10 → 20        # Balance speed/accuracy

# Upgrade:
image: mongo:6 → mongo:8
```

With these changes, gtdevvin would likely give **9-10 visitors** (similar to gtvin but with better tracking from frame=10).

---

## What Should You Do?

### Quick Answer:

**Question**: Which branch should I use?

**Answer**: 
- **For production NOW**: Use **gtvin** (current branch)
  - Optimized through extensive testing
  - MongoDB 8 compatible
  - Fast (frame=30)
  - 82-91% accuracy (9-10 visitors)

- **For gtdevvin branch**: Update it with gtvin's learnings
  - Change threshold from 0.71 → 0.6435
  - Add missing parameters
  - Upgrade to MongoDB 8
  - Keep frame=10 if you want better tracking

---

## Migration Command (gtdevvin → gtvin settings)

If you want to update gtdevvin branch:

```bash
# Switch to gtdevvin branch
git checkout gtdevvin

# Copy optimized settings from gtvin
# Edit docker-compose.yolov11.yml and apply changes above

# Or use this sed script:
sed -i 's/REID_SIM_THRESHOLD=0.71/REID_SIM_THRESHOLD=0.6435/' docker-compose.yolov11.yml
sed -i 's/FEATURE_AVG_WINDOW=5/FEATURE_AVG_WINDOW=11/' docker-compose.yolov11.yml
sed -i 's/REID_GALLERY_TTL_SECONDS=60/REID_GALLERY_TTL_SECONDS=3600/' docker-compose.yolov11.yml
sed -i 's/mongo:6/mongo:8/' docker-compose.yolov11.yml

# Add missing parameters (manual edit required)
# Then test
```

---

## Summary

| Aspect | gtdevvin (old) | gtvin (current) | Winner |
|--------|----------------|-----------------|--------|
| Threshold tuning | ❌ 0.71 (too strict) | ✅ 0.6435 (optimized) | **gtvin** |
| Parameters | ❌ Missing rerank/handoff | ✅ Complete | **gtvin** |
| MongoDB | mongo:6 | ✅ mongo:8 + fixes | **gtvin** |
| Frame rate | 10 (slower) | 30 (faster) | Depends |
| Testing | ❌ Not tuned | ✅ Extensively tested | **gtvin** |

**Recommendation**: Use **gtvin** (current branch) or update gtdevvin with gtvin's learnings.

---

## Files to Reference

- `REID_MODEL_COMPARISON.md` - OSNet vs FastReID
- `REID_TUNING_GUIDE.md` - Parameter guide
- `MONGODB8_UPGRADE.md` - MongoDB 8 migration
- `INVESTIGATION_12_VS_13_COUNT.md` - Counting investigation

All the learnings from today's session! 🎯

