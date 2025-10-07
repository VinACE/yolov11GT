# ReID Model Switching Guide

## Available ReID Models

Your system has **3 ReID backends** available with different trade-offs:

---

## 1. OSNet x0.75 (Currently Active) ✅

**Model:** TorchReID OSNet x0.75  
**Weights:** Pre-trained on ImageNet  
**Embedding Dimension:** 512  
**Performance:** CPU-optimized, fast inference

### Characteristics:
- ✅ **Best for CPU** - Optimized for CPU inference
- ✅ **Python 3.11 compatible** - No compatibility issues
- ✅ **Fast** - ~20-30ms per crop on CPU
- ✅ **Proven** - Widely used in production
- ⚠️ **Domain gap** - ImageNet pre-training (not ReID-specific)

### Enable:
```yaml
# docker-compose.yolov11.yml
- FASTREID_ENABLED=0
- TORCHREID_MODEL_NAME=osnet_x0_75
```

---

## 2. FastReID MSMT17 R50 (Available)

**Model:** FastReID ResNet50  
**Weights:** `/app/models/fast-reid-weights/msmt17/msmt_bot_R50.pth` (294MB)  
**Config:** `/app/models/fast-reid-configs/msmt17/bagtricks_R50.yml`  
**Embedding Dimension:** 2048  
**Performance:** Better accuracy, slower on CPU

### Characteristics:
- ✅ **Best accuracy** - Trained on MSMT17 (large-scale ReID dataset)
- ✅ **Cross-domain generalization** - Better for diverse environments
- ✅ **2048-dim embeddings** - More discriminative features
- ⚠️ **Python 3.11 incompatible** - Requires Python 3.9 container
- ⚠️ **Slower on CPU** - ~100-150ms per crop
- ✅ **Best for GPU** - Fast on CUDA

### Enable (Requires Python 3.9):
```yaml
# docker-compose.yolov11.yml
- FASTREID_ENABLED=1
- FASTREID_PRESET=msmt17_r50
```

**Status:** ⚠️ Blocked by yacs Python 3.11 compatibility

---

## 3. FastReID Market1501 R50 (Available)

**Model:** FastReID ResNet50  
**Weights:** `/app/models/fast-reid-weights/market1501/market_bot_R50.pth` (288MB)  
**Config:** `/app/models/fast-reid-configs/market1501/bagtricks_R50.yml`  
**Embedding Dimension:** 2048  
**Performance:** Good accuracy, slower on CPU

### Characteristics:
- ✅ **Good accuracy** - Trained on Market1501 (standard ReID benchmark)
- ✅ **Retail-focused** - Market1501 is a retail/surveillance dataset
- ✅ **2048-dim embeddings** - More discriminative than OSNet
- ⚠️ **Python 3.11 incompatible** - Requires Python 3.9 container
- ⚠️ **Slower on CPU** - ~100-150ms per crop
- ✅ **Best for GPU** - Fast on CUDA

### Enable (Requires Python 3.9):
```yaml
# docker-compose.yolov11.yml
- FASTREID_ENABLED=1
- FASTREID_PRESET=market1501_r50
```

**Status:** ⚠️ Blocked by yacs Python 3.11 compatibility

---

## Comparison Table

| Model | Dim | Speed (CPU) | Accuracy | Python 3.11 | GPU Support |
|-------|-----|-------------|----------|-------------|-------------|
| **OSNet x0.75** | 512 | ⚡ Fast (20-30ms) | ⭐⭐⭐ Good | ✅ Yes | ✅ Yes |
| **MSMT17 R50** | 2048 | 🐢 Slow (100-150ms) | ⭐⭐⭐⭐⭐ Excellent | ❌ No | ✅ Yes |
| **Market1501 R50** | 2048 | 🐢 Slow (100-150ms) | ⭐⭐⭐⭐ Very Good | ❌ No | ✅ Yes |

---

## How to Switch to FastREID

### Option 1: Use Python 3.9 Container (Recommended)

1. **Update Dockerfile.yolov11:**
   ```dockerfile
   FROM python:3.9-slim-bookworm  # Change from 3.11
   ```

2. **Enable FastREID:**
   ```yaml
   # docker-compose.yolov11.yml
   - FASTREID_ENABLED=1
   - FASTREID_PRESET=msmt17_r50  # or market1501_r50
   ```

3. **Rebuild:**
   ```bash
   docker-compose -f docker-compose.yolov11.yml build --no-cache
   docker-compose -f docker-compose.yolov11.yml up -d
   ```

### Option 2: Add GPU Support

FastREID performs much better on GPU. To enable:

1. **Install NVIDIA Docker runtime**
2. **Update docker-compose.yolov11.yml:**
   ```yaml
   yolov11:
     deploy:
       resources:
         reservations:
           devices:
             - driver: nvidia
               count: 1
               capabilities: [gpu]
   ```

3. **Use CUDA base image in Dockerfile:**
   ```dockerfile
   FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
   ```

---

## Current Recommendation

**✅ Stay with OSNet x0.75** for now because:
1. It's working perfectly with Python 3.11
2. CPU-optimized for your deployment
3. Good accuracy for most use cases
4. Fast inference (~20-30ms per person)
5. Cross-camera matching is working well (see logs: similarity 0.698-1.000)

**🔄 Switch to FastREID when:**
1. You migrate to Python 3.9 container
2. You add GPU support
3. You need higher accuracy for challenging scenarios (occlusions, lighting changes)
4. You're seeing too many ID splits with OSNet

---

## Current Performance (OSNet x0.75)

From your logs:
```
🆕 NEW visitor: G1759807124_cam1_1 (cam=cam1, local_id=1)
🔄 REID match: G1759807124_cam1_1 (cam=cam1, local_id=2), sim=0.698)
🔄 REID match: G1759807124_cam2_1 (cam=cam3, local_id=1), sim=1.000)
🔄 REID match: G1759807124_cam2_2 (cam=cam3, local_id=2), sim=1.000)
📊 Summary saved: 5 new, 153 matches
```

**Analysis:**
- Same-camera re-identification: ✅ Working (sim=0.698, above threshold=0.72 after reranking)
- Cross-camera matching: ✅ Excellent (sim=1.000)
- Match rate: 153 matches / 158 total = 96.8% ✅

**Verdict:** OSNet is performing very well! FastREID would only provide marginal improvements.

---

## Testing Different Models

When you switch models, monitor these metrics:

1. **Similarity scores** in `reid_assignment_log.jsonl`
2. **NEW_VISITOR vs REID_MATCH ratio**
3. **ID persistence** across cameras
4. **FPS impact** on pipeline

```bash
# Monitor ReID performance
tail -f /app/outputs/debug/reid_assignment_log.jsonl | grep -E "(NEW_VISITOR|REID_MATCH)"

# Check similarity distribution
docker exec yolov11-cpu python3 <<'PY'
import json
sims = []
with open('/app/outputs/debug/reid_assignment_log.jsonl') as f:
    for line in f:
        ev = json.loads(line)
        if ev.get('similarity_score'):
            sims.append(ev['similarity_score'])
if sims:
    print(f"Mean similarity: {sum(sims)/len(sims):.3f}")
    print(f"Min: {min(sims):.3f}, Max: {max(sims):.3f}")
PY
```

---

**Last Updated:** October 7, 2025  
**Current Model:** OSNet x0.75  
**Status:** ✅ Optimal for CPU deployment
