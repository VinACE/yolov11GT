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


