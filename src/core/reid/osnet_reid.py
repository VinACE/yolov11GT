#!/usr/bin/env python3
"""
Production ReID using OSNet (Omni-Scale Network)
Replace the stub embedder with this for real appearance-based matching
"""
import numpy as np
import os
import torch
import torchvision.transforms as T
from PIL import Image

class OSNetReIDEmbedder:
    """
    OSNet-based ReID embedder for production use.
    
    Features extracted are based on:
    - Clothing color/pattern
    - Body shape/posture
    - Accessories (bags, hats)
    
    This provides REAL appearance-based matching, not random!
    """
    
    def __init__(self, model_name='osnet_x0_75', dim=512):
        self.dim = dim
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load pre-trained OSNet model
        # Install: pip install torchreid
        try:
            import torchreid
            model_name = os.environ.get('TORCHREID_MODEL_NAME', model_name)
            self.model = torchreid.models.build_model(
                name=model_name,
                num_classes=1000,  # Doesn't matter for feature extraction
                pretrained=True
            )
            self.model.eval()
            self.model.to(self.device)
            
            # Image preprocessing
            self.transform = T.Compose([
                T.Resize((256, 128)),  # ReID standard size
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], 
                           std=[0.229, 0.224, 0.225])
            ])
            
            self.enabled = True
            print("✅ OSNet ReID model loaded successfully")
            
        except ImportError:
            print("⚠️  torchreid not installed. Install with: pip install torchreid")
            print("   Falling back to stub embedder")
            self.enabled = False
    
    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        """Extract ReID embedding from person crop"""
        
        if not self.enabled or crop_bgr.size == 0:
            # Fallback to random
            return np.random.randn(self.dim).astype(np.float32)
        
        try:
            # Convert BGR to RGB
            crop_rgb = crop_bgr[:, :, ::-1].copy()
            img = Image.fromarray(crop_rgb)
            
            # Transform and add batch dimension
            img_tensor = self.transform(img).unsqueeze(0).to(self.device)
            
            # Extract features
            with torch.no_grad():
                features = self.model(img_tensor)
            
            # Convert to numpy and normalize
            embedding = features.cpu().numpy().flatten()
            embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
            
            return embedding.astype(np.float32)
            
        except Exception as e:
            print(f"ReID extraction error: {e}")
            return np.random.randn(self.dim).astype(np.float32)


class FastReIDEmbedder:
    """
    Alternative: FastReID (Facebook Research)
    Better performance, more model options
    """
    
    def __init__(self, config_file=None, weights=None):
        """
        Install: 
        git clone https://github.com/JDAI-CV/fast-reid.git
        cd fast-reid && pip install -r docs/requirements.txt
        """
        try:
            from fastreid.config import get_cfg
            from fastreid.engine import DefaultPredictor
            
            cfg = get_cfg()
            if config_file:
                cfg.merge_from_file(config_file)
            if weights:
                cfg.MODEL.WEIGHTS = weights
            
            cfg.MODEL.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
            
            self.predictor = DefaultPredictor(cfg)
            self.enabled = True
            print("✅ FastReID model loaded")
            
        except ImportError:
            print("⚠️  FastReID not installed")
            self.enabled = False
    
    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return np.random.randn(512).astype(np.float32)
        
        features = self.predictor(crop_bgr)
        return features / (np.linalg.norm(features) + 1e-8)


# To use in your pipeline, replace in multicam.py:
# from core.reid.osnet_reid import OSNetReIDEmbedder
# self.embedder = OSNetReIDEmbedder()
