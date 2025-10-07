# Real-Time Configuration ✅

## Current Settings (Optimized for CPU Real-Time)

### Performance Settings:
```yaml
- FRAME_PROCESS_EVERY=30        # Process every 30th frame (~1 FPS from 30 FPS video)
- FASTREID_ENABLED=0            # Using OSNet x0.75 (fast on CPU)
- TORCHREID_MODEL_NAME=osnet_x0_75
```

### ReID Parameters (Tuned for OSNet):
```yaml
- REID_SIM_THRESHOLD=0.65       # Lower for OSNet's similarity range
- REID_RERANK_ALPHA=0.40        # Moderate EMA weighting
- REID_RERANK_MARGIN=0.04       # Margin for ambiguity rejection
- FEATURE_AVG_WINDOW=8          # Smooth over 8 detections
- MIN_CROP_HEIGHT=120           # Accept crops ≥120px
- REID_GALLERY_TTL_SECONDS=3600 # 1 hour retention (no expiry during video)
```

### Camera Configuration:
```python
cameras = {
    "cam1": "/app/data/demo3.mp4",
    "cam2": "/app/data/Sample.mp4",
    "cam3": "/app/data/SampleGT.mp4",  # Identical to cam2 for testing
}
```

---

## N-Stream FAISS Architecture

### How Cross-Camera Matching Works:

1. **Shared ReID Gallery** (FAISS Index):
   ```
   orchestrator.reid_index = ReidIndex(dim=512)  # ONE index for ALL cameras
   ```

2. **Every Detection Queries the ENTIRE Gallery**:
   ```python
   # When cam2 detects a person:
   candidates = self.reid_index.search_topk(embedding, topk=5)
   # This searches ALL embeddings from cam1, cam2, cam3
   ```

3. **Cross-Camera Matching Flow**:
   ```
   Frame N:
   - cam1 detects person A → creates G001_cam1_1, adds embedding to gallery
   
   Frame N+1:
   - cam2 detects same person A → searches gallery
   - Finds G001_cam1_1 with similarity=0.98
   - Matches! Assigns G001_cam1_1 to cam2 detection
   ```

4. **Identical Video Testing** (cam2 & cam3):
   ```
   - cam2 frame 100: person B detected → G002_cam2_5
   - cam3 frame 100: SAME person B → searches gallery
   - Finds G002_cam2_5 with similarity≈1.0
   - Matches! Assigns G002_cam2_5 to cam3
   ```

### Architecture Diagram:
```
┌─────────┐  ┌─────────┐  ┌─────────┐
│  cam1   │  │  cam2   │  │  cam3   │
│ demo3   │  │ Sample  │  │SampleGT │
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └────────────┼────────────┘
                  │
         ┌────────▼────────┐
         │ YOLOv11 Detect  │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │ OSNet Embed     │
         │ (512-dim)       │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │  FAISS Index    │ ◄─── SHARED across ALL cameras
         │  (cosine sim)   │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │ Global ID       │
         │ Assignment      │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │    MongoDB      │
         └─────────────────┘
```

---

## Expected Performance

### OSNet x0.75 on CPU:

| Metric | Value |
|--------|-------|
| **Embedding time** | 20-30ms per person |
| **Frame processing** | ~150-200ms (5 people × 3 cams) |
| **Effective FPS** | 5-7 FPS ✅ Real-time capable |
| **Accuracy** | Good (0.65-0.75 similarity range) |
| **Unique count** | Expected: 11-13 visitors |

### With FRAME_PROCESS_EVERY=30:
- Skip 29 frames, process 1
- From 30 FPS video → process at 1 FPS
- Very low CPU load
- Still captures all unique people (they appear in multiple frames)

---

## Scaling to Real-Time Production

### For 3 Cameras at 30 FPS:

**Option A: OSNet + Frame Skipping (Current)**
- ✅ Works on CPU
- FRAME_PROCESS_EVERY=30 (1 FPS effective)
- Adequate for counting and dwell time
- ⚠️ Not suitable for real-time tracking visualization

**Option B: OSNet + More Frames**
- FRAME_PROCESS_EVERY=5-10
- ~3-6 FPS effective
- Better for real-time dashboards
- Requires more CPU cores

**Option C: GPU + FastREID**
- ✅ Best accuracy
- ✅ Can process every frame (30 FPS)
- ✅ Real-time tracking
- Requires: NVIDIA GPU, CUDA

---

## Test Current Configuration

Run:
```bash
./run_services.sh
```
Select option **6**

This will give you:
- **OSNet x0.75** (512-dim, fast)
- **FRAME_PROCESS_EVERY=30** (~1 FPS)
- **3 cameras** with shared FAISS gallery
- **Non-looping** (stops after videos finish)

Expected result: **11-12 unique visitors** in ~1-2 minutes

---

**Status:** ✅ Configured for CPU real-time with OSNet  
**Processing Speed:** ~1 FPS (FRAME_PROCESS_EVERY=30)  
**Accuracy:** Good for visitor counting & dwell time
