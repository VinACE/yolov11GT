# FaceNet Docker Setup - Complete Explanation

**Date**: October 10, 2025  
**Question**: How is FaceNet installed and picked up in docker-compose?

---

## ✅ What's Actually Installed

### 1. **FaceNet Package** (facenet-pytorch)

#### Dockerfile.yolov11 (Line 119):
```dockerfile
RUN pip install --no-cache-dir \
    torchreid \
    gdown \
    facenet-pytorch  # ← Installed here
```

#### requirements.txt (Line 56):
```
facenet-pytorch>=2.6.0  # Hybrid ReID (FaceNet + OSNet)
```

#### Verification:
```bash
$ docker exec yolov11-cpu pip list | grep facenet
facenet-pytorch  2.6.0  ✅ INSTALLED
```

**Status**: ✅ **Package IS installed in the Docker image**

---

### 2. **Docker-Compose Configuration**

#### docker-compose.yolov11.yml (Line 48):
```yaml
environment:
  - USE_HYBRID_REID=1  # Enable hybrid FaceNet + OSNet mode
```

#### Verification:
```bash
$ docker exec yolov11-cpu env | grep HYBRID
USE_HYBRID_REID=1  ✅ SET
```

**Status**: ✅ **Environment variable IS configured**

---

## ❌ What's NOT Working

### The Critical Issue: **Model Weights**

**FaceNet requires 2 things:**
1. ✅ Python package (`facenet-pytorch`) - INSTALLED
2. ❌ Pretrained weights (~110MB file) - **NOT CACHED**

When you try to use FaceNet, line 49 of `facenet_embedder.py` runs:

```python
self.facenet = InceptionResnetV1(pretrained='vggface2').eval()
```

**What happens:**
1. Checks cache: `/root/.cache/torch/hub/checkpoints/`
2. No weights found → tries to download from internet
3. Network unreachable/timeout
4. **FaceNet initialization FAILS**
5. Falls back to stub embedder

---

## 🔍 Current Pipeline Reality

### Test Results:

```bash
=== Testing FaceNet Installation ===
1. Package installed: ✅ facenet_pytorch OK
2. Can import classes: ✅ InceptionResnetV1  
3. Can load model (requires download): ❌ FAILED: Connection timed out
4. Checking cache: ❌ No vggface2 weights cached

=== Simulating Pipeline Initialization ===
⚠️  FaceNet initialization error: Connection timed out
⚠️  Could not load OSNet: Network is unreachable
⚠️  Hybrid mode: FaceNet disabled, using ReID only
✅ HybridEmbedder loaded
   - Face enabled: False  ← NOT USING FACENET!
   - Dimension: 512
   - Using: ReidEmbedder  ← USING STUB (random)!
```

### What's ACTUALLY Running:

```
Pipeline Process:
├── HybridEmbedder (initialized)
│   ├── FaceNet: ❌ Failed (no weights)
│   ├── OSNet: ❌ Failed (no weights)
│   └── Fallback: ✅ ReidEmbedder (STUB - random embeddings)
└── Result: NOT using real ReID!
```

---

## 🤔 But Why High Similarity Scores?

You saw similarity scores of 0.93-1.0 in the logs. Here's why:

### The Videos Are Identical!

```bash
$ md5sum /app/data/Sample.mp4 /app/data/SampleGT.mp4
<same hash>  Sample.mp4
<same hash>  SampleGT.mp4
```

**Sample.mp4 and SampleGT.mp4 are THE SAME FILE**

With stub embedder:
- Same frame → same person crop → same dimensions
- Crop dimensions used as random seed
- Identical crops → identical random embeddings
- Result: Perfect 1.0 similarity!

**The high scores don't prove ReID is working - they prove the videos are identical!**

---

## 📦 Cached Models Found

```bash
Found models:
- /app/models/fast-reid-weights/msmt17/msmt_bot_R50.pth (293.8 MB)
- /app/models/fast-reid-weights/market1501/market_bot_R50.pth (287.0 MB)

Not found:
- FaceNet vggface2 weights (~110MB)
- OSNet x0_75 weights (~9MB)
```

**FastREID models exist but aren't being used** (FASTREID_ENABLED=0)

---

## 🔧 How to Fix This

### Solution 1: Download Model Weights (RECOMMENDED)

The models need to be downloaded when internet is available, then cached.

#### Step 1: Enable internet temporarily and download weights

```bash
# Inside container with internet access:
docker exec yolov11-cpu python3 -c "
from facenet_pytorch.models.inception_resnet_v1 import InceptionResnetV1
import torchreid

print('Downloading FaceNet vggface2 weights...')
model = InceptionResnetV1(pretrained='vggface2')
print('✅ FaceNet weights cached')

print('Downloading OSNet x0_75 weights...')
osnet = torchreid.models.build_model(
    name='osnet_x0_75',
    num_classes=1000,
    loss='softmax',
    pretrained=True
)
print('✅ OSNet weights cached')

print('Weights saved to: /root/.cache/torch/')
"
```

#### Step 2: Copy weights to persistent volume

```bash
# From host:
docker exec yolov11-cpu tar -czf /tmp/model_cache.tar.gz /root/.cache/torch/
docker cp yolov11-cpu:/tmp/model_cache.tar.gz ./models/
```

#### Step 3: Update Dockerfile to restore cache

```dockerfile
# Add to Dockerfile.yolov11 after RUN pip install facenet-pytorch
COPY models/model_cache.tar.gz /tmp/
RUN tar -xzf /tmp/model_cache.tar.gz -C / && rm /tmp/model_cache.tar.gz
```

#### Step 4: Rebuild image

```bash
docker-compose -f docker-compose.yolov11.yml build yolov11
docker-compose -f docker-compose.yolov11.yml up -d
```

---

### Solution 2: Mount Model Cache (QUICK FIX)

Download weights once, then mount as volume:

```yaml
# docker-compose.yolov11.yml
services:
  yolov11:
    volumes:
      - ./model_cache:/root/.cache/torch:ro  # ← Add this
```

---

### Solution 3: Use FastREID (Already Downloaded)

FastREID weights ARE cached! Enable them:

```yaml
# docker-compose.yolov11.yml
environment:
  - FASTREID_ENABLED=1  # Enable FastREID
  - USE_HYBRID_REID=0   # Disable hybrid (broken)
```

**Trade-off**: Slower (100-150ms vs 30-50ms) but actually works!

---

## 📋 Quick Verification Script

Save this as `verify_reid.sh`:

```bash
#!/bin/bash
echo "=== Verifying ReID Setup ==="

echo "1. Checking FaceNet package..."
docker exec yolov11-cpu pip show facenet-pytorch | grep Version

echo "2. Checking environment..."
docker exec yolov11-cpu env | grep -E "(HYBRID|FASTREID)"

echo "3. Checking cached models..."
docker exec yolov11-cpu bash -c "
  find /root/.cache/torch -name '*.pth' 2>/dev/null | wc -l
  find /app/models -name '*.pth' 2>/dev/null | wc -l
"

echo "4. Testing embedder..."
docker exec yolov11-cpu python3 -c "
import sys
sys.path.insert(0, '/app/src')
from core.reid.facenet_embedder import HybridEmbedder
embedder = HybridEmbedder()
print(f'Face enabled: {embedder.face_enabled}')
print(f'Embedder type: {type(embedder.reid_embedder).__name__}')
"
```

---

## ✅ Summary: How FaceNet IS and ISN'T Working

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| **facenet-pytorch package** | ✅ Installed | Dockerfile line 119 | In Docker image |
| **requirements.txt** | ✅ Listed | Line 56 | Version 2.6.0+ |
| **docker-compose env** | ✅ Set | Line 48 | USE_HYBRID_REID=1 |
| **Package in container** | ✅ Present | pip list | facenet-pytorch 2.6.0 |
| **vggface2 weights** | ❌ Missing | Should be in cache | Need download |
| **osnet weights** | ❌ Missing | Should be in cache | Need download |
| **HybridEmbedder** | ⚠️ Fallback | Loads but disabled | Using stub! |
| **Actual ReID** | ❌ Not working | Using random embeddings | FIX NEEDED |

---

## 🎯 Recommended Action

**OPTION A: Download Weights Now** (if internet available)
```bash
./download_reid_weights.sh  # Create this script with Solution 1
```

**OPTION B: Use FastREID** (weights already exist)
```bash
# Edit docker-compose.yolov11.yml:
- FASTREID_ENABLED=1
- USE_HYBRID_REID=0

# Restart:
docker-compose -f docker-compose.yolov11.yml restart yolov11
```

**OPTION C: Test with Different Videos**
Your current test is misleading because Sample.mp4 == SampleGT.mp4. Use different videos to see real ReID performance!

---

**Bottom Line**: 

- ✅ FaceNet package IS installed in Docker
- ✅ Environment IS configured in docker-compose  
- ❌ Model weights are NOT cached
- ❌ Pipeline IS NOT using real ReID
- ✅ Solution: Download weights OR use FastREID

The setup is correct, but needs the model weight files!



