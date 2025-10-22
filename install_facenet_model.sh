#!/bin/bash
# Install FaceNet model weights from downloaded file
# Usage: ./install_facenet_model.sh <path_to_vggface2.pth>

set -e

FACENET_FILE="${1:-/home/vinsent_120232/Downloads/vggface2.pth}"

echo "=========================================="
echo "📦 Installing FaceNet Model Weights"
echo "=========================================="
echo ""

# Check if file exists
if [ ! -f "$FACENET_FILE" ]; then
    echo "❌ FaceNet file not found: $FACENET_FILE"
    echo ""
    echo "Please provide the path to the vggface2.pth file:"
    echo "  ./install_facenet_model.sh /path/to/vggface2.pth"
    echo ""
    echo "Or download it and save to:"
    echo "  /home/vinsent_120232/Downloads/vggface2.pth"
    echo ""
    exit 1
fi

# Check file size (should be around 100-110MB)
SIZE_MB=$(du -m "$FACENET_FILE" | cut -f1)
echo "Found: $FACENET_FILE (${SIZE_MB}MB)"

if [ "$SIZE_MB" -lt 50 ]; then
    echo "⚠️  Warning: File seems too small (${SIZE_MB}MB)"
    echo "   Expected: ~107MB"
    read -p "Continue anyway? (y/n): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

echo ""
echo "Creating torch cache directory in container..."
docker exec yolov11-cpu mkdir -p /root/.cache/torch/hub/checkpoints

echo "Copying FaceNet weights to container..."
docker cp "$FACENET_FILE" yolov11-cpu:/root/.cache/torch/hub/checkpoints/vggface2.pth

echo ""
echo "Verifying installation..."
docker exec yolov11-cpu ls -lh /root/.cache/torch/hub/checkpoints/

echo ""
echo "Testing FaceNet loading..."
docker exec yolov11-cpu python3 << 'PYEOF'
from facenet_pytorch.models.inception_resnet_v1 import InceptionResnetV1
import torch

try:
    print("Loading FaceNet with vggface2 weights...")
    model = InceptionResnetV1(pretrained='vggface2').eval()
    print("✅ FaceNet loaded successfully from cache!")
    
    # Test inference
    dummy_input = torch.randn(1, 3, 160, 160)
    with torch.no_grad():
        output = model(dummy_input)
    print(f"✅ Test inference successful: output shape {output.shape}")
    
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()
PYEOF

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ FaceNet Installed Successfully!"
    echo "=========================================="
    echo ""
    echo "Both models are now installed:"
    docker exec yolov11-cpu ls -lh /root/.cache/torch/checkpoints/ /root/.cache/torch/hub/checkpoints/ 2>/dev/null | grep "\.pth"
    echo ""
    echo "Next step: Test hybrid embedder"
    echo "  ./test_hybrid_embedder.sh"
    echo ""
else
    echo ""
    echo "❌ Installation failed. Check errors above."
    exit 1
fi



