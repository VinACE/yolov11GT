#!/bin/bash
# Download FaceNet and OSNet model weights for hybrid ReID
# This needs to be run when internet connection is available

set -e

echo "=========================================="
echo "🔽 Downloading ReID Model Weights"
echo "=========================================="
echo ""
echo "This will download:"
echo "  - FaceNet vggface2 weights (~110MB)"
echo "  - OSNet x0_75 weights (~9MB)"
echo "  - Total: ~120MB download"
echo ""
echo "⚠️  Requires internet connection!"
echo ""

# Check if container is running
if ! docker ps | grep -q yolov11-cpu; then
    echo "❌ Container yolov11-cpu is not running"
    echo "   Start it first: docker-compose -f docker-compose.yolov11.yml up -d"
    exit 1
fi

echo "📦 Container is running. Starting download..."
echo ""

# Download weights inside container
docker exec yolov11-cpu bash -c '
set -e

echo "1️⃣  Downloading FaceNet vggface2 weights..."
python3 << "PYEOF"
import sys
sys.path.insert(0, "/app/src")

try:
    from facenet_pytorch.models.inception_resnet_v1 import InceptionResnetV1
    import torch
    
    print("   Initializing FaceNet (this will download ~110MB)...")
    model = InceptionResnetV1(pretrained="vggface2")
    print("   ✅ FaceNet vggface2 weights downloaded!")
    
    # Verify it worked
    cache_dir = torch.hub.get_dir() + "/checkpoints"
    print(f"   Cached in: {cache_dir}")
    
except Exception as e:
    print(f"   ❌ Failed: {e}")
    sys.exit(1)
PYEOF

echo ""
echo "2️⃣  Downloading OSNet x0_75 weights..."
python3 << "PYEOF"
import sys
sys.path.insert(0, "/app/src")

try:
    import torchreid
    import warnings
    warnings.filterwarnings("ignore")
    
    print("   Initializing OSNet (this will download ~9MB)...")
    model = torchreid.models.build_model(
        name="osnet_x0_75",
        num_classes=1000,
        loss="softmax",
        pretrained=True
    )
    print("   ✅ OSNet x0_75 weights downloaded!")
    
except Exception as e:
    print(f"   ❌ Failed: {e}")
    sys.exit(1)
PYEOF

echo ""
echo "3️⃣  Verifying downloads..."
python3 << "PYEOF"
import pathlib
import sys

cache_paths = [
    pathlib.Path.home() / ".cache" / "torch" / "hub" / "checkpoints",
    pathlib.Path.home() / ".cache" / "torch" / "checkpoints",
]

found = False
for p in cache_paths:
    if p.exists():
        files = list(p.glob("*.pth"))
        if files:
            total_size = sum(f.stat().st_size for f in files) / (1024*1024)
            print(f"   Found {len(files)} model files ({total_size:.1f} MB)")
            for f in files:
                size_mb = f.stat().st_size / (1024*1024)
                print(f"   ✅ {f.name} ({size_mb:.1f} MB)")
            found = True
            break

if not found:
    print("   ❌ No model weights found!")
    sys.exit(1)
PYEOF

echo ""
echo "4️⃣  Testing hybrid embedder..."
python3 << "PYEOF"
import sys
sys.path.insert(0, "/app/src")
import os
os.environ["USE_HYBRID_REID"] = "1"

from core.reid.facenet_embedder import HybridEmbedder
import numpy as np

print("   Initializing HybridEmbedder...")
embedder = HybridEmbedder()

print(f"   - Face enabled: {embedder.face_enabled}")
print(f"   - Dimension: {embedder.dim}")
print(f"   - ReID embedder: {type(embedder.reid_embedder).__name__}")

# Test embedding
test_crop = np.random.randint(0, 255, (128, 64, 3), dtype=np.uint8)
import time
start = time.time()
emb = embedder.embed(test_crop)
elapsed = (time.time() - start) * 1000

print(f"   - Test embedding: {emb.shape}, {elapsed:.1f}ms")

if embedder.face_enabled:
    print("   ✅ Hybrid ReID is FULLY OPERATIONAL!")
else:
    print("   ⚠️  FaceNet still not enabled (check errors above)")
PYEOF
'

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Model Weights Downloaded Successfully!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Restart the pipeline:"
    echo "   docker-compose -f docker-compose.yolov11.yml restart yolov11"
    echo ""
    echo "2. Or rebuild to make weights permanent:"
    echo "   ./rebuild_with_facenet.sh"
    echo ""
    echo "3. Verify hybrid ReID is working:"
    echo "   ./run_services.sh → Option 5 (Quick Test)"
    echo ""
else
    echo ""
    echo "❌ Download failed! Check errors above."
    echo ""
    echo "Common issues:"
    echo "  - No internet connection"
    echo "  - Firewall blocking downloads"
    echo "  - Network timeout"
    echo ""
    echo "You can try:"
    echo "  - Checking internet: ping google.com"
    echo "  - Running again with more time"
    echo "  - Downloading manually and copying to container"
    exit 1
fi



