#!/bin/bash
# Rebuild Docker image with FaceNet permanently installed

set -e

echo "=========================================="
echo "🔨 Rebuilding Docker Image with FaceNet"
echo "=========================================="
echo ""

echo "This will:"
echo "  1. Rebuild the Docker image with facenet-pytorch"
echo "  2. Recreate containers with new image"
echo "  3. FaceNet will persist across all restarts!"
echo ""
read -p "Continue? (y/n): " confirm

if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "🛑 Stopping containers..."
docker-compose -f docker-compose.yolov11.yml down

echo ""
echo "🔨 Building new image (this may take 5-10 minutes)..."
echo "   Installing: torch, torchvision, torchreid, facenet-pytorch, FastReID"
echo ""

# Build with cache bust to force fresh build
docker-compose -f docker-compose.yolov11.yml build --build-arg CACHE_BUST=$(date +%s) yolov11

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Image built successfully!"
    echo ""
    echo "🚀 Starting containers with new image..."
    docker-compose -f docker-compose.yolov11.yml up -d
    
    echo ""
    echo "⏳ Waiting for containers to start..."
    sleep 5
    
    echo ""
    echo "🧪 Testing FaceNet is installed..."
    docker exec yolov11-cpu python3 -c "
import facenet_pytorch
print('✅ FaceNet version:', facenet_pytorch.__version__)
print('✅ FaceNet is permanently installed!')
"
    
    echo ""
    echo "=========================================="
    echo "✅ Rebuild Complete!"
    echo "=========================================="
    echo ""
    echo "FaceNet is now PERMANENTLY installed"
    echo "It will persist across all container restarts!"
    echo ""
    echo "Services:"
    echo "  - FastAPI: http://localhost:8000"
    echo "  - Streamlit: http://localhost:8501"
    echo ""
    echo "To start your pipeline:"
    echo "  ./run_services.sh"
    echo ""
else
    echo ""
    echo "❌ Build failed! Check errors above."
    exit 1
fi


