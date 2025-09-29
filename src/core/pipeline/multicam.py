from typing import Dict, Any, List
import cv2
import numpy as np
from datetime import datetime

from core.detection.yolo import YoloV11Detector
from core.segmentation.sam import SamSegmenter
from core.tracking.tracker import SimpleTracker
from core.reid.embedding import ReidEmbedder, ReidIndex
from core.storage.db import get_db
from core.storage.models import Visitor, VisitEvent


class MultiCameraOrchestrator:
    def __init__(self, camera_sources: Dict[str, str]) -> None:
        self.camera_sources = camera_sources
        self.detector = YoloV11Detector()
        self.segmenter = SamSegmenter()
        self.tracker_by_cam = {cid: SimpleTracker() for cid in camera_sources}
        self.embedder = ReidEmbedder()
        self.reid_index = ReidIndex()

    def _extract_crop(self, frame: np.ndarray, bbox: List[float]) -> np.ndarray:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
        return frame[y1:y2, x1:x2].copy()

    def process_frame(self, camera_id: str, frame_bgr: np.ndarray) -> None:
        dt_now = datetime.utcnow()
        dets = self.detector.detect(frame_bgr)
        dets = self.segmenter.segment_from_bboxes(frame_bgr, dets)
        dets = self.tracker_by_cam[camera_id].update(dets)

        with get_db() as db:
            for d in dets:
                crop = self._extract_crop(frame_bgr, d["bbox"])
                emb = self.embedder.embed(crop)
                match = self.reid_index.search(emb, topk=1)
                if match is None or (match is not None and match[1] < 0.7):
                    global_id = f"G{dt_now.timestamp():.0f}_{camera_id}_{d['local_id']}"
                    self.reid_index.add(global_id, emb)
                    visitor = Visitor(global_id=global_id, first_seen_at=dt_now, last_seen_at=dt_now)
                    db.add(visitor)
                    db.flush()
                    visit = VisitEvent(visitor_id=visitor.id, camera_id=camera_id, in_time=dt_now)
                    db.add(visit)
                else:
                    global_id = match[0]
                    visitor = db.query(Visitor).filter_by(global_id=global_id).first()
                    if visitor:
                        visitor.last_seen_at = dt_now
                db.commit()


