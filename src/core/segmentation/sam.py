from typing import List, Dict, Any
import numpy as np


class SamSegmenter:
    """Stub for SAM segmenter. Replace with actual SAM implementation as needed."""

    def __init__(self) -> None:
        pass

    def segment_from_bboxes(self, image_bgr: np.ndarray, detections: List[Dict[str, Any]]):
        # Placeholder: return same detections with dummy masks
        for d in detections:
            d["mask"] = None
        return detections


