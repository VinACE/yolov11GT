#!/bin/bash
# Ensure FaceNet is installed on container start (temporary workaround)
# This can be added to container startup until image is rebuilt

# Check if facenet-pytorch is installed
if python3 -c "import facenet_pytorch" 2>/dev/null; then
    echo "✅ FaceNet already installed"
else
    echo "📦 FaceNet not found, installing..."
    pip install facenet-pytorch --quiet
    echo "✅ FaceNet installed"
fi


