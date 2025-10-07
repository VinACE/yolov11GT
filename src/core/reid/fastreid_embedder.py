import numpy as np
import cv2
import os
import torch
from pathlib import Path

class FastReIDEmbedder:
    """FastReID wrapper for person re-identification.
    
    Loads FastReID models (MSMT17 or Market1501 R50) for high-quality embeddings.
    Falls back to random embeddings if model loading fails.
    """

    def __init__(self) -> None:
        self.dim = 2048  # ResNet50 feature dimension
        self.enabled = os.environ.get("FASTREID_ENABLED", "0") == "1"
        self.predictor = None
        
        if not self.enabled:
            print("ℹ️  FastReID disabled (FASTREID_ENABLED=0)")
            return
            
        # Optional runtime-configurable model selection
        self.config_path = os.environ.get("FASTREID_CONFIG", "")
        self.weights_path = os.environ.get("FASTREID_WEIGHTS", "")
        
        # Simple preset mapping if explicit paths are not set
        preset = os.environ.get("FASTREID_PRESET", "").lower()
        if not self.config_path or not self.weights_path:
            if preset == "msmt17_r50":
                # Prefer existing weights file among common names
                self.config_path = self.config_path or "/app/models/fast-reid-configs/msmt17/bagtricks_R50.yml"
                msmt_weight_candidates = [
                    "/app/models/fast-reid-weights/msmt17/msmt_bot_R50.pth",
                    "/app/models/fast-reid-weights/msmt17/bagtricks_R50.pth",
                ]
                for p in msmt_weight_candidates:
                    if Path(p).exists():
                        self.weights_path = p
                        break
                if not self.weights_path:
                    self.weights_path = msmt_weight_candidates[0]
            elif preset == "market1501_r50":
                self.config_path = self.config_path or "/app/models/fast-reid-configs/market1501/bagtricks_R50.yml"
                market_weight_candidates = [
                    "/app/models/fast-reid-weights/market1501/market_bot_R50.pth",
                    "/app/models/fast-reid-weights/market1501/bagtricks_R50.pth",
                ]
                for p in market_weight_candidates:
                    if Path(p).exists():
                        self.weights_path = p
                        break
                if not self.weights_path:
                    self.weights_path = market_weight_candidates[0]
        
        # Try to load the model
        try:
            from fastreid.config import get_cfg
            from fastreid.engine import DefaultPredictor
            
            if not Path(self.config_path).exists():
                raise FileNotFoundError(f"FastReID config not found: {self.config_path}")
            if not Path(self.weights_path).exists():
                raise FileNotFoundError(f"FastReID weights not found: {self.weights_path}")
            
            cfg = get_cfg()
            cfg.merge_from_file(self.config_path)
            cfg.MODEL.WEIGHTS = self.weights_path
            cfg.MODEL.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
            
            self.predictor = DefaultPredictor(cfg)
            
            msg = "✅ FastReID model loaded"
            if self.config_path:
                msg += f" | config={Path(self.config_path).name}"
            if self.weights_path:
                msg += f" | weights={Path(self.weights_path).name}"
            if preset:
                msg += f" | preset={preset}"
            msg += f" | device={cfg.MODEL.DEVICE}"
            print(msg)
            
        except Exception as e:
            print(f"⚠️  FastReID load failed: {e}")
            print("   Falling back to random embeddings for testing")
            self.enabled = False

    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        if not self.enabled or self.predictor is None:
            # Fallback to random embeddings
            rng = np.random.default_rng(seed=int(crop_bgr.size) % 2**32)
            vec = rng.random(self.dim).astype(np.float32)
            vec /= (np.linalg.norm(vec) + 1e-8)
            return vec
        
        # Real FastReID inference
        try:
            # FastReID expects BGR input
            features = self.predictor(crop_bgr)
            # Extract features and normalize
            if isinstance(features, torch.Tensor):
                vec = features.cpu().numpy().flatten()
            else:
                vec = np.array(features).flatten()
            
            # L2 normalize
            norm = np.linalg.norm(vec)
            if norm > 1e-8:
                vec = vec / norm
            
            return vec.astype(np.float32)
            
        except Exception as e:
            print(f"⚠️  FastReID inference error: {e}, using fallback")
            rng = np.random.default_rng(seed=int(crop_bgr.size) % 2**32)
            vec = rng.random(self.dim).astype(np.float32)
            vec /= (np.linalg.norm(vec) + 1e-8)
            return vec


