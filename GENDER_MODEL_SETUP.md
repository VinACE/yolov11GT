# Gender Model Setup Guide

**Goal**: Add lightweight gender classification to improve ReID accuracy  
**Priority**: Fast CPU inference (<30ms per person)

---

## Recommended: OpenCV DNN Gender Model (Best for CPU)

### Why This Model?

✅ **Extremely lightweight** (~1MB)  
✅ **Fast on CPU** (~5-10ms per person)  
✅ **Pre-trained** (no training needed)  
✅ **Easy integration** (OpenCV already installed)  
✅ **Good accuracy** (~90-95% on frontal faces)

### Download Commands

```bash
cd /home/vinsent_120232/proj/yolov11/models

# Download gender classification model (Caffe format)
wget https://github.com/GilLevi/AgeGenderDeepLearning/raw/master/models/gender_net.caffemodel
wget https://raw.githubusercontent.com/GilLevi/AgeGenderDeepLearning/master/models/deploy_gender.prototxt

# Rename for clarity
mv deploy_gender.prototxt gender_deploy.prototxt
mv gender_net.caffemodel gender_model.caffemodel

# Verify downloads
ls -lh gender_*
```

**Model Details:**
- Architecture: CNN (3 conv layers)
- Input: 227x227 RGB
- Output: [male_prob, female_prob]
- Size: ~1MB
- Speed: 5-10ms on CPU

---

## Alternative: Age-Gender-Estimation (More Modern)

If you want a more modern model:

```bash
cd /home/vinsent_120232/proj/yolov11/models

# Download ONNX model for age and gender
wget https://github.com/onnx/models/raw/main/validated/vision/body_analysis/age_gender/models/age_googlenet.onnx
wget https://github.com/onnx/models/raw/main/validated/vision/body_analysis/age_gender/models/gender_googlenet.onnx
```

---

## Implementation Code

Update `src/core/reid/gender_classifier.py`:

```python
import cv2
import numpy as np
import os
from typing import Tuple

class GenderClassifier:
    def __init__(self, confidence_threshold: float = 0.6):
        self.confidence_threshold = confidence_threshold
        self.enabled = int(os.environ.get("GENDER_CLASSIFICATION_ENABLED", "1")) == 1
        self.model = None
        
        if self.enabled:
            # Load OpenCV DNN gender model
            model_dir = "/app/models"
            prototxt = f"{model_dir}/gender_deploy.prototxt"
            caffemodel = f"{model_dir}/gender_model.caffemodel"
            
            if os.path.exists(prototxt) and os.path.exists(caffemodel):
                self.model = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
                print(f"✅ Gender model loaded (OpenCV DNN)")
            else:
                print(f"⚠️ Gender model files not found, using fallback")
                self.enabled = False
    
    def classify(self, crop_bgr: np.ndarray) -> Tuple[str, float]:
        if not self.enabled or self.model is None or crop_bgr.size == 0:
            return ('unknown', 0.0)
        
        try:
            # Preprocess for gender model
            blob = cv2.dnn.blobFromImage(
                crop_bgr, 
                scalefactor=1.0,
                size=(227, 227),
                mean=(78.4263377603, 87.7689143744, 114.895847746),
                swapRB=False
            )
            
            # Run inference
            self.model.setInput(blob)
            preds = self.model.forward()
            
            # Get gender (0=male, 1=female)
            gender_idx = preds[0].argmax()
            confidence = float(preds[0][gender_idx])
            
            gender = 'male' if gender_idx == 0 else 'female'
            
            # Return unknown if confidence too low
            if confidence < self.confidence_threshold:
                return ('unknown', confidence)
            
            return (gender, confidence)
            
        except Exception as e:
            print(f"⚠️ Gender classification error: {e}")
            return ('unknown', 0.0)
```

---

## Quick Setup Script

Create this script to download and setup:

```bash
#!/bin/bash
# setup_gender_model.sh

echo "Downloading OpenCV DNN Gender Model..."
cd /home/vinsent_120232/proj/yolov11/models

# Download model files
wget -q https://github.com/GilLevi/AgeGenderDeepLearning/raw/master/models/gender_net.caffemodel \
  -O gender_model.caffemodel

wget -q https://raw.githubusercontent.com/GilLevi/AgeGenderDeepLearning/master/models/deploy_gender.prototxt \
  -O gender_deploy.prototxt

# Verify
if [ -f "gender_model.caffemodel" ] && [ -f "gender_deploy.prototxt" ]; then
    echo "✅ Gender model downloaded successfully"
    ls -lh gender_*
else
    echo "❌ Download failed"
    exit 1
fi

echo ""
echo "To enable:"
echo "1. Update gender_classifier.py with the code above"
echo "2. Restart: docker-compose -f docker-compose.yolov11.yml restart yolov11"
echo "3. Test and verify gender classification working"
```

---

## Alternative: HuggingFace Model (Easy but Heavier)

If you prefer a modern transformer-based model:

```bash
# Add to requirements.txt or install
pip install transformers

# In gender_classifier.py:
from transformers import pipeline

class GenderClassifier:
    def __init__(self):
        # Use pre-trained model from HuggingFace
        self.model = pipeline(
            "image-classification",
            model="rizvandwiki/gender-classification"
        )
    
    def classify(self, crop_bgr):
        # Convert BGR to RGB
        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        results = self.model(crop_rgb)
        # Parse results
        gender = results[0]['label'].lower()
        confidence = results[0]['score']
        return (gender, confidence)
```

**Performance**: ~50-100ms (slower but accurate)

---

## Recommendation Matrix

| Model | Size | Speed | Accuracy | Integration | Recommended |
|-------|------|-------|----------|-------------|-------------|
| **OpenCV DNN** | 1MB | 5-10ms | 90-95% | Easy | ✅ **Best for you** |
| HuggingFace | 50MB+ | 50-100ms | 95%+ | Easy | Good but slow |
| FairFace | 90MB | 30-50ms | 95%+ | Medium | Good alternative |
| DeepFace | 100MB+ | 100ms+ | 95%+ | Easy | Too slow |

---

## Quick Start (Recommended)

Run these commands:

```bash
# 1. Download model
cd /home/vinsent_120232/proj/yolov11/models
wget https://github.com/GilLevi/AgeGenderDeepLearning/raw/master/models/gender_net.caffemodel -O gender_model.caffemodel
wget https://raw.githubusercontent.com/GilLevi/AgeGenderDeepLearning/master/models/deploy_gender.prototxt -O gender_deploy.prototxt

# 2. Verify download
ls -lh gender_*
```

Then I'll update the gender_classifier.py code for you!

---

## Expected Impact

**Current**: 9 visitors (with crop=100) or 13 (with crop=140)  
**With crop=120**: Likely 10-12 visitors  
**With crop=120 + Gender**: May reach 11 visitors! ✅

Gender will help if:
- Some of the merged/split people are different genders
- Prevents cross-gender false matches

---

**Want me to download the model and update the code for you?** Just say yes and I'll do it! 🚀

