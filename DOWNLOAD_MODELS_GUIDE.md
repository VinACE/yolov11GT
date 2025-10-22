# Download ReID Model Weights - Quick Guide

**Purpose**: Download FaceNet and OSNet weights for hybrid ReID

---

## 🚀 Quick Start

### Step 1: Run the download script

```bash
./download_reid_weights.sh
```

**What it does:**
- Downloads FaceNet vggface2 weights (~110MB)
- Downloads OSNet x0_75 weights (~9MB)
- Verifies downloads succeeded
- Tests the hybrid embedder

**Requirements:**
- ✅ Container must be running
- ✅ Internet connection required
- ⏱️  Takes 2-5 minutes depending on connection speed

---

### Step 2: Restart pipeline

```bash
# Option A: Restart just the yolov11 service
docker-compose -f docker-compose.yolov11.yml restart yolov11

# Option B: Restart pipeline process only (faster)
docker exec yolov11-cpu pkill -f run_pipeline
docker exec -d yolov11-cpu bash -c "cd /app && python scripts/run_pipeline.py"
```

---

### Step 3: Verify it worked

```bash
./run_services.sh
# Select option 5 (Quick Test)
```

**Expected output:**
```
3️⃣  Testing ReID embedders...
   ✅ OSNet working! Embedding shape: (512,)
   ✅ FaceNet working! Embedding shape: (512,)  ← Should see this!
```

---

## 📋 Manual Download (if script fails)

If the automatic script doesn't work, download manually:

### Inside container:

```bash
docker exec -it yolov11-cpu bash

# Download FaceNet weights
python3 << 'EOF'
from facenet_pytorch.models.inception_resnet_v1 import InceptionResnetV1
print("Downloading FaceNet vggface2...")
model = InceptionResnetV1(pretrained='vggface2')
print("Done!")
EOF

# Download OSNet weights
python3 << 'EOF'
import torchreid
print("Downloading OSNet x0_75...")
model = torchreid.models.build_model(
    name='osnet_x0_75',
    num_classes=1000,
    loss='softmax',
    pretrained=True
)
print("Done!")
EOF

exit
```

---

## 💾 Make Weights Persistent (Optional)

By default, weights are cached in `/root/.cache/torch/` inside the container.

**Problem**: Weights are lost if container is recreated!

**Solution**: Copy weights to mounted volume

```bash
# 1. Create directory for model cache
mkdir -p ./model_cache

# 2. Copy weights from container
docker exec yolov11-cpu bash -c "
  tar -czf /tmp/torch_cache.tar.gz /root/.cache/torch/
"
docker cp yolov11-cpu:/tmp/torch_cache.tar.gz ./model_cache/

# 3. Add to docker-compose.yolov11.yml:
# volumes:
#   - ./model_cache/torch:/root/.cache/torch:ro

# 4. Restart container
docker-compose -f docker-compose.yolov11.yml restart yolov11
```

---

## 🔍 Verify Downloads

### Check cached files:

```bash
docker exec yolov11-cpu bash -c "
  ls -lh /root/.cache/torch/hub/checkpoints/ 2>/dev/null || 
  ls -lh /root/.cache/torch/checkpoints/ 2>/dev/null
"
```

**Expected:**
```
-rw-r--r-- 1 root root 107M Oct 10 15:00 vggface2.pth
-rw-r--r-- 1 root root 8.8M Oct 10 15:01 osnet_x0_75_*.pth
```

### Test embedders:

```bash
docker exec yolov11-cpu python3 << 'EOF'
import sys
sys.path.insert(0, '/app/src')
import os
os.environ['USE_HYBRID_REID'] = '1'

from core.reid.facenet_embedder import HybridEmbedder
embedder = HybridEmbedder()

print(f"✅ Face enabled: {embedder.face_enabled}")
print(f"✅ Dimension: {embedder.dim}")
print(f"✅ Using: {type(embedder.reid_embedder).__name__}")
EOF
```

**Expected output:**
```
✅ FaceNet model loaded successfully
   - Device: cpu
   - Speed: ~10-30ms per person
   - Accuracy: 99%+ (when face is visible)
✅ OSNet production ReID (512-dim, CPU-optimized)
✅ Face enabled: True  ← Should be True!
✅ Dimension: 512
✅ Using: OSNetReIDEmbedder
```

---

## ⚠️ Troubleshooting

### Problem: Network timeout

```
URLError: <urlopen error [Errno 110] Connection timed out>
```

**Solutions:**
1. Check internet: `ping google.com`
2. Check firewall/proxy settings
3. Try again (sometimes servers are slow)
4. Download on different machine and copy files

---

### Problem: Container not running

```
❌ Container yolov11-cpu is not running
```

**Solution:**
```bash
docker-compose -f docker-compose.yolov11.yml up -d
./download_reid_weights.sh
```

---

### Problem: Weights downloaded but not working

**Check environment variable:**
```bash
docker exec yolov11-cpu env | grep HYBRID
# Should show: USE_HYBRID_REID=1
```

**Restart pipeline:**
```bash
docker-compose -f docker-compose.yolov11.yml restart yolov11
```

---

## 📊 Before vs After

### Before (No Weights):
```
HybridEmbedder loaded
   - Face enabled: False          ❌
   - Using: ReidEmbedder          ❌ (stub/random)
   - Similarity: Random/misleading
```

### After (With Weights):
```
HybridEmbedder loaded
   - Face enabled: True           ✅
   - Using: OSNetReIDEmbedder     ✅ (real ReID)
   - Similarity: Accurate 93-98%
```

---

## 📁 File Sizes Reference

| Model | File | Size | Purpose |
|-------|------|------|---------|
| FaceNet | vggface2.pth | ~107MB | Face recognition |
| OSNet | osnet_x0_75_*.pth | ~9MB | Person ReID |
| FastREID | msmt_bot_R50.pth | ~294MB | Already cached |
| FastREID | market_bot_R50.pth | ~287MB | Already cached |

---

## ✅ Success Checklist

- [ ] Run `./download_reid_weights.sh`
- [ ] See "✅ Model Weights Downloaded Successfully!"
- [ ] Restart pipeline
- [ ] Run quick test (option 5)
- [ ] See "✅ FaceNet working!"
- [ ] Check pipeline logs for "✅ Using Hybrid ReID"

---

## 🎯 Next Steps After Download

1. **Test with real videos** (not identical ones)
2. **Monitor ReID accuracy** in logs
3. **Check processing speed** (should be ~26ms avg)
4. **Optionally make weights persistent** (see above)

---

**Questions?** Check `FACENET_DOCKER_SETUP_EXPLAINED.md` for detailed explanation.



