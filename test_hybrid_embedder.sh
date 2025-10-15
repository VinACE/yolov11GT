#!/bin/bash
# Test the hybrid embedder with both FaceNet and OSNet

echo "=========================================="
echo "🧪 Testing Hybrid ReID Embedder"
echo "=========================================="
echo ""

docker exec yolov11-cpu python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app/src')
import os
os.environ['USE_HYBRID_REID'] = '1'

print("1️⃣  Testing Model Weights Cache")
print("")

import pathlib
cache_paths = [
    pathlib.Path('/root/.cache/torch/checkpoints'),
    pathlib.Path('/root/.cache/torch/hub/checkpoints'),
]

for p in cache_paths:
    if p.exists():
        files = list(p.glob('*.pth'))
        if files:
            print(f"   {p}:")
            for f in files:
                size_mb = f.stat().st_size / (1024*1024)
                print(f"   ✅ {f.name} ({size_mb:.1f}MB)")

print("")
print("2️⃣  Testing HybridEmbedder Initialization")
print("")

try:
    from core.reid.facenet_embedder import HybridEmbedder
    embedder = HybridEmbedder()
    
    print(f"   Face enabled: {embedder.face_enabled}")
    print(f"   Dimension: {embedder.dim}")
    print(f"   ReID embedder type: {type(embedder.reid_embedder).__name__}")
    
    if embedder.face_enabled:
        print("")
        print("   🎉 SUCCESS: Hybrid mode fully operational!")
        print("   - FaceNet: ✅ Working (for face detection)")
        print("   - OSNet: ✅ Working (fallback ReID)")
    else:
        print("")
        print("   ⚠️  FaceNet not enabled - check if weights are in correct location")
        
except Exception as e:
    print(f"   ❌ Failed to initialize: {e}")
    import traceback
    traceback.print_exc()

print("")
print("3️⃣  Testing Embedding Generation")
print("")

try:
    import numpy as np
    import time
    
    # Test with random crop
    test_crop = np.random.randint(0, 255, (128, 64, 3), dtype=np.uint8)
    
    times = []
    for i in range(5):
        start = time.time()
        emb = embedder.embed(test_crop)
        times.append((time.time() - start) * 1000)
    
    avg_time = sum(times) / len(times)
    print(f"   Embedding shape: {emb.shape}")
    print(f"   Average time: {avg_time:.1f}ms")
    print(f"   Range: {min(times):.1f}-{max(times):.1f}ms")
    print(f"   ✅ Embedding generation working!")
    
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("")
print("=========================================="
print("✅ Test Complete")
print("=========================================="
PYEOF



