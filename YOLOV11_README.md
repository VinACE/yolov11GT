# YOLOv11 CPU Docker Setup

This Docker setup provides a complete YOLOv11 environment optimized for CPU inference.

## Features

- **YOLOv11**: Latest version with CPU-optimized PyTorch
- **OpenCV**: For image processing and visualization
- **Pre-installed models**: YOLOv11n (nano) model ready to use
- **Additional tools**: matplotlib, seaborn, pandas for data analysis
- **Jupyter support**: Optional Jupyter Lab for interactive development

## Quick Start

### 1. Build and Run with Docker Compose

```bash
# Build and start the container
docker-compose -f docker-compose.yolov11.yml up -d

# Check if everything is working
docker-compose -f docker-compose.yolov11.yml exec yolov11 python /app/test_yolov11.py
```

### 2. Manual Docker Build

```bash
# Build the image
docker build -f Dockerfile.yolov11 -t yolov11-cpu .

# Run the container
docker run -it --rm \
  -v $(pwd)/data:/app/data:ro \
  -v $(pwd)/outputs:/app/outputs \
  yolov11-cpu
```

## Usage Examples

### Basic Inference

```bash
# Run inference on an image
docker-compose -f docker-compose.yolov11.yml exec yolov11 \
  python /app/inference.py --image /app/data/your_image.jpg

# With custom model
docker-compose -f docker-compose.yolov11.yml exec yolov11 \
  python /app/inference.py --image /app/data/your_image.jpg --model /app/models/your_model.pt
```

### Interactive Python Session

```bash
# Start an interactive session
docker-compose -f docker-compose.yolov11.yml exec yolov11 python

# Then in Python:
from ultralytics import YOLO
import cv2

# Load model
model = YOLO('yolo11n.pt')

# Run inference
results = model('path/to/your/image.jpg')

# View results
results[0].show()
```

### Jupyter Lab (Optional)

```bash
# Start Jupyter Lab
docker-compose -f docker-compose.yolov11.yml --profile jupyter up -d yolov11-jupyter

# Access at http://localhost:8888
```

## Directory Structure

```
/app/
├── data/          # Input images (mounted from host)
├── outputs/       # Results and annotated images
├── models/        # Custom YOLOv11 models
├── test_yolov11.py    # Installation test script
└── inference.py       # Basic inference script
```

## Available YOLOv11 Models

The container comes with YOLOv11n pre-installed. You can also use:

- `yolo11n.pt` - Nano (fastest, smallest)
- `yolo11s.pt` - Small
- `yolo11m.pt` - Medium
- `yolo11l.pt` - Large
- `yolo11x.pt` - Extra Large (most accurate)

Download additional models:

```python
from ultralytics import YOLO
model = YOLO('yolo11s.pt')  # Downloads automatically
```

## Performance Notes

- **CPU Optimized**: Uses PyTorch CPU version for maximum compatibility
- **Memory Efficient**: YOLOv11n uses ~6MB model size
- **Fast Inference**: Optimized for CPU inference without GPU dependencies
- **Resource Limits**: Docker compose includes CPU and memory limits

## Troubleshooting

### Test Installation

```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 python /app/test_yolov11.py
```

### Check Available Models

```bash
docker-compose -f docker-compose.yolov11.yml exec yolov11 ls -la /app/models/
```

### View Container Logs

```bash
docker-compose -f docker-compose.yolov11.yml logs yolov11
```

## Customization

### Install Additional Packages

Add to the Dockerfile:

```dockerfile
RUN pip install --no-cache-dir your-package-name
```

### Use Custom Models

1. Place your `.pt` model files in the `./models/` directory
2. Reference them in inference scripts: `--model /app/models/your_model.pt`

### Environment Variables

- `YOLO_VERBOSE=True` - Enable verbose YOLOv11 output
- `YOLO_CACHE_DIR=/app/models` - Set model cache directory

## Example Scripts

### Batch Processing

```python
import os
from ultralytics import YOLO

model = YOLO('yolo11n.pt')
input_dir = '/app/data'
output_dir = '/app/outputs'

for filename in os.listdir(input_dir):
    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        image_path = os.path.join(input_dir, filename)
        results = model(image_path)
        results[0].save(os.path.join(output_dir, f'result_{filename}'))
```

### Video Processing

```python
from ultralytics import YOLO

model = YOLO('yolo11n.pt')
results = model('/app/data/video.mp4')
results[0].save('/app/outputs/result_video.mp4')
```
