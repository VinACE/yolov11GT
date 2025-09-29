from typing import List, Dict, Any
import numpy as np

from ultralytics import YOLO


class YoloV11Detector:
    def __init__(self, model_path: str = "yolo11n.pt", conf: float = 0.25) -> None:
        self.model = YOLO(model_path)
        self.conf = conf

    def detect(self, image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        results = self.model.predict(image_bgr, conf=self.conf, verbose=False)
        detections: List[Dict[str, Any]] = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for b in boxes:
                cls_id = int(b.cls[0]) if getattr(b, "cls", None) is not None else -1
                # cls 0 is person in COCO
                if cls_id != 0:
                    continue
                xyxy = b.xyxy[0].tolist()
                conf = float(b.conf[0]) if getattr(b, "conf", None) is not None else 0.0
                detections.append({
                    "bbox": xyxy,  # [x1, y1, x2, y2]
                    "conf": conf,
                    "class_id": cls_id,
                })
        return detections


