import numpy as np
import cv2
import os

class FastReIDEmbedder:
    """Optional FastReID wrapper.

    This is a light placeholder that expects a command-line or service-based FastReID
    inference in production. For now, it returns None to indicate unavailable unless
    FASTREID_ENABLED=1 is set and a proper integration is provided.
    """

    def __init__(self) -> None:
        self.dim = 512
        self.enabled = os.environ.get("FASTREID_ENABLED", "0") == "1"
        # Optional runtime-configurable model selection
        self.config_path = os.environ.get("FASTREID_CONFIG", "")
        self.weights_path = os.environ.get("FASTREID_WEIGHTS", "")
        # Simple preset mapping if explicit paths are not set
        preset = os.environ.get("FASTREID_PRESET", "").lower()
        if self.enabled and (not self.config_path or not self.weights_path) and preset:
            if preset == "msmt17_r50":
                # Prefer existing weights file among common names
                self.config_path = self.config_path or "/app/models/fast-reid-configs/msmt17/bagtricks_R50.yml"
                msmt_weight_candidates = [
                    "/app/models/fast-reid-weights/msmt17/msmt_bot_R50.pth",
                    "/app/models/fast-reid-weights/msmt17/bagtricks_R50.pth",
                ]
                for p in msmt_weight_candidates:
                    if os.path.exists(p):
                        self.weights_path = p
                        break
                if not self.weights_path:
                    self.weights_path = msmt_weight_candidates[-1]
            elif preset == "market1501_r50":
                self.config_path = self.config_path or "/app/models/fast-reid-configs/market1501/bagtricks_R50.yml"
                market_weight_candidates = [
                    "/app/models/fast-reid-weights/market1501/market_bot_R50.pth",
                    "/app/models/fast-reid-weights/market1501/bagtricks_R50.pth",
                ]
                for p in market_weight_candidates:
                    if os.path.exists(p):
                        self.weights_path = p
                        break
                if not self.weights_path:
                    self.weights_path = market_weight_candidates[-1]
        if self.enabled:
            msg = "✅ FastReID enabled"
            if self.config_path:
                msg += f" | config={self.config_path}"
            if self.weights_path:
                msg += f" | weights={self.weights_path}"
            if preset:
                msg += f" | preset={preset}"
            print(msg)

    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        if not self.enabled:
            raise RuntimeError("FastReID not enabled; set FASTREID_ENABLED=1 and provide integration")
        # Placeholder: In a real integration, call FastReID model here.
        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        # TODO: replace with real inference
        rng = np.random.default_rng(seed=int(crop_rgb.size) % 2**32)
        vec = rng.random(self.dim).astype(np.float32)
        vec /= (np.linalg.norm(vec) + 1e-8)
        return vec


