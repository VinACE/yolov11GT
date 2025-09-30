from typing import Dict, Any, List
import cv2
import numpy as np
from datetime import datetime
import json
import os
from pathlib import Path

from core.detection.yolo import YoloV11Detector
from core.segmentation.sam import SamSegmenter
from core.tracking.tracker import SimpleTracker
from core.reid.embedding import ReidEmbedder, ReidIndex
from core.storage.db import get_db
from core.storage.models import Visitor, VisitEvent

# Try to import production ReID, fallback to stub if unavailable
try:
    from core.reid.osnet_reid import OSNetReIDEmbedder
    OSNET_AVAILABLE = True
except ImportError:
    OSNET_AVAILABLE = False
    print("⚠️  OSNet ReID not available, using stub embedder")


class MultiCameraOrchestrator:
    def __init__(self, camera_sources: Dict[str, str], debug_dir: str = "/app/outputs/debug", use_osnet: bool = True) -> None:
        self.camera_sources = camera_sources
        self.detector = YoloV11Detector()
        self.segmenter = SamSegmenter()
        self.tracker_by_cam = {cid: SimpleTracker() for cid in camera_sources}
        
        # Initialize ReID embedder - try OSNet first, fallback to stub
        if use_osnet and OSNET_AVAILABLE:
            try:
                self.embedder = OSNetReIDEmbedder()
                print("✅ Using OSNet production ReID (appearance-based)")
            except Exception as e:
                print(f"⚠️  OSNet failed to load: {e}")
                print("   Falling back to stub ReID embedder")
                self.embedder = ReidEmbedder()
        else:
            self.embedder = ReidEmbedder()
            if not use_osnet:
                print("ℹ️  Using stub ReID embedder (use_osnet=False)")
            else:
                print("ℹ️  Using stub ReID embedder (OSNet not available)")
        
        # Initialize ReID index with the embedding dimensionality
        embed_dim = getattr(self.embedder, "dim", 256)
        self.reid_index = ReidIndex(dim=embed_dim)
        
        # Debug and logging setup
        self.debug_dir = Path(debug_dir)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for organized logging
        (self.debug_dir / "detections").mkdir(exist_ok=True)
        (self.debug_dir / "reid_assignments").mkdir(exist_ok=True)
        (self.debug_dir / "annotated_frames").mkdir(exist_ok=True)
        
        # Logging files
        self.detection_log = self.debug_dir / "detection_log.jsonl"
        self.reid_log = self.debug_dir / "reid_assignment_log.jsonl"
        self.summary_log = self.debug_dir / "summary.json"
        
        # Frame counter
        self.frame_count = {cid: 0 for cid in camera_sources}
        
        # Statistics
        self.stats = {
            "total_detections": 0,
            "new_visitors": 0,
            "reid_matches": 0,
            "cameras": list(camera_sources.keys())
        }
        
        print(f"📁 Debug logging enabled at: {self.debug_dir}")
        print(f"   - Detection logs: {self.detection_log}")
        print(f"   - ReID logs: {self.reid_log}")

    def _extract_crop(self, frame: np.ndarray, bbox: List[float]) -> np.ndarray:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
        return frame[y1:y2, x1:x2].copy()

    def _log_detection(self, camera_id: str, frame_num: int, detections: List[Dict], timestamp: datetime) -> None:
        """Log detection results to file"""
        log_entry = {
            "timestamp": timestamp.isoformat(),
            "camera_id": camera_id,
            "frame_number": frame_num,
            "num_detections": len(detections),
            "detections": [
                {
                    "local_id": d.get("local_id", "N/A"),
                    "bbox": d["bbox"],
                    "confidence": d.get("conf", 0.0)
                }
                for d in detections
            ]
        }
        
        with open(self.detection_log, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def _log_reid_assignment(self, camera_id: str, frame_num: int, local_id: int, 
                            global_id: str, is_new: bool, similarity: float, timestamp: datetime) -> None:
        """Log ReID assignment to file"""
        log_entry = {
            "timestamp": timestamp.isoformat(),
            "camera_id": camera_id,
            "frame_number": frame_num,
            "local_id": local_id,
            "global_id": global_id,
            "assignment_type": "NEW_VISITOR" if is_new else "REID_MATCH",
            "similarity_score": similarity,
            "reid_index_size": len(self.reid_index.global_ids)
        }
        
        with open(self.reid_log, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        # Update stats
        if is_new:
            self.stats["new_visitors"] += 1
        else:
            self.stats["reid_matches"] += 1
    
    def _save_annotated_frame(self, frame: np.ndarray, camera_id: str, frame_num: int, 
                             detections: List[Dict]) -> None:
        """Save annotated frame with bboxes and IDs"""
        annotated = frame.copy()
        
        for d in detections:
            x1, y1, x2, y2 = [int(v) for v in d["bbox"]]
            local_id = d.get("local_id", "?")
            global_id = d.get("global_id", "N/A")
            
            # Draw thicker bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
            
            # Draw background rectangle for better text visibility
            label_local = f"Local: {local_id}"
            label_global = f"Global: {global_id[:20]}"
            
            # Calculate text sizes
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.0
            thickness = 2
            
            (w1, h1), _ = cv2.getTextSize(label_local, font, font_scale, thickness)
            (w2, h2), _ = cv2.getTextSize(label_global, font, font_scale, thickness)
            
            max_width = max(w1, w2)
            total_height = h1 + h2 + 20
            
            # Draw semi-transparent background
            overlay = annotated.copy()
            cv2.rectangle(overlay, (x1, y1 - total_height - 10), (x1 + max_width + 20, y1), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, annotated, 0.4, 0, annotated)
            
            # Draw text in bright colors
            cv2.putText(annotated, label_local, (x1 + 5, y1 - h2 - 15), 
                       font, font_scale, (0, 255, 255), thickness)  # Yellow
            cv2.putText(annotated, label_global, (x1 + 5, y1 - 5), 
                       font, font_scale, (0, 255, 0), thickness)  # Green
        
        # Add frame info at top
        info_text = f"Camera: {camera_id} | Frame: {frame_num} | Detections: {len(detections)}"
        cv2.putText(annotated, info_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        
        # Save every frame so IDs can be cross-verified frame-by-frame
        output_path = self.debug_dir / "annotated_frames" / f"{camera_id}_frame_{frame_num:06d}.jpg"
        cv2.imwrite(str(output_path), annotated)
    
    def process_frame(self, camera_id: str, frame_bgr: np.ndarray) -> None:
        dt_now = datetime.utcnow()
        self.frame_count[camera_id] += 1
        frame_num = self.frame_count[camera_id]
        
        # Detection
        dets = self.detector.detect(frame_bgr)
        dets = self.segmenter.segment_from_bboxes(frame_bgr, dets)
        dets = self.tracker_by_cam[camera_id].update(dets)
        
        self.stats["total_detections"] += len(dets)
        
        # Log detections
        self._log_detection(camera_id, frame_num, dets, dt_now)
        
        # Frame index log (for DB cross-verification)
        frame_index_path = self.debug_dir / "frame_global_ids.csv"

        # Process each detection for ReID
        processed_dets = []
        with get_db() as db:
            for d in dets:
                crop = self._extract_crop(frame_bgr, d["bbox"])
                emb = self.embedder.embed(crop)
                match = self.reid_index.search(emb, topk=1)
                
                if match is None or (match is not None and match[1] < 0.7):
                    # New visitor detected
                    global_id = f"G{dt_now.timestamp():.0f}_{camera_id}_{d['local_id']}"
                    self.reid_index.add(global_id, emb)
                    
                    # Log ReID assignment
                    self._log_reid_assignment(
                        camera_id, frame_num, d['local_id'], global_id, 
                        is_new=True, similarity=0.0, timestamp=dt_now
                    )
                    
                    visitor = Visitor(global_id=global_id, first_seen_at=dt_now, last_seen_at=dt_now)
                    db.add(visitor)
                    db.flush()
                    visit = VisitEvent(visitor_id=visitor.id, camera_id=camera_id, in_time=dt_now)
                    db.add(visit)
                    
                    d["global_id"] = global_id
                    print(f"🆕 NEW visitor: {global_id} (cam={camera_id}, local_id={d['local_id']})")
                else:
                    # Existing visitor - ReID match
                    global_id = match[0]
                    similarity = match[1]
                    
                    # Log ReID assignment
                    self._log_reid_assignment(
                        camera_id, frame_num, d['local_id'], global_id,
                        is_new=False, similarity=similarity, timestamp=dt_now
                    )
                    
                    visitor = db.query(Visitor).filter_by(global_id=global_id).first()
                    if visitor:
                        visitor.last_seen_at = dt_now
                        # Update the most recent open visit event for this visitor
                        open_visit = db.query(VisitEvent).filter(
                            VisitEvent.visitor_id == visitor.id,
                            VisitEvent.out_time.is_(None)
                        ).first()
                        if open_visit:
                            # Still in premises, keep updating last_seen
                            pass
                    
                    d["global_id"] = global_id
                    print(f"🔄 REID match: {global_id} (cam={camera_id}, local_id={d['local_id']}, sim={similarity:.3f})")
                
                processed_dets.append(d)
                db.commit()

        # Append a row for each detection in this frame
        try:
            is_new_file = not frame_index_path.exists()
            with open(frame_index_path, "a") as f:
                if is_new_file:
                    f.write("timestamp,camera_id,frame_number,local_id,global_id,x1,y1,x2,y2\n")
                for d in processed_dets:
                    x1,y1,x2,y2 = [int(v) for v in d["bbox"]]
                    f.write(f"{dt_now.isoformat()},{camera_id},{frame_num},{d.get('local_id','')},{d.get('global_id','')},{x1},{y1},{x2},{y2}\n")
        except Exception:
            pass
        
        # Save annotated frame periodically
        self._save_annotated_frame(frame_bgr, camera_id, frame_num, processed_dets)
        
        # Save summary stats periodically
        if frame_num % 100 == 0:
            self._save_summary()
    
    def _save_summary(self) -> None:
        """Save summary statistics to file"""
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_frames_processed": sum(self.frame_count.values()),
            "frames_per_camera": self.frame_count,
            "statistics": self.stats,
            "reid_database_size": len(self.reid_index.global_ids),
            "known_global_ids": self.reid_index.global_ids
        }
        
        with open(self.summary_log, "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"📊 Summary saved: {self.stats['new_visitors']} new, {self.stats['reid_matches']} matches")


