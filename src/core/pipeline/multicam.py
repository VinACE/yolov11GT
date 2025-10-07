from typing import Dict, Any, List
from collections import deque, defaultdict
import cv2
import numpy as np
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

from core.detection.yolo import YoloV11Detector
from core.segmentation.sam import SamSegmenter
from core.tracking.tracker import StrongSortLite
from core.reid.embedding import ReidEmbedder, ReidIndex
from core.storage.mongo import get_mongo_db, upsert_visitor, insert_visit_event, close_open_visit
_mongo_db = get_mongo_db()

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
        self.tracker_by_cam = {cid: StrongSortLite() for cid in camera_sources}
        
        # Initialize ReID embedder - prefer FastReID if enabled, else OSNet, else stub
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

        # Try FastReID if explicitly enabled
        try:
            from core.reid.fastreid_embedder import FastReIDEmbedder
            fre = FastReIDEmbedder()
            if getattr(fre, 'enabled', False):
                self.embedder = fre
                print("✅ Using FastReID embedder")
        except Exception as e:
            print(f"ℹ️  FastReID not enabled/available: {e}")
        
        # Initialize ReID index with the embedding dimensionality
        embed_dim = getattr(self.embedder, "dim", 256)
        self.reid_index = ReidIndex(dim=embed_dim)
        # Configure EMA momentum and TTL if provided
        ema_m = float(os.environ.get("REID_EMA_MOMENTUM", "0.9"))
        ttl_s = int(os.environ.get("REID_GALLERY_TTL_SECONDS", "60"))
        self.reid_index.set_ema_momentum(ema_m)
        self.reid_index.set_ttl_seconds(ttl_s)
        
        # Visitor exit timeout – mark visitor as exited if not seen for N seconds
        # You can override via env var VISITOR_TIMEOUT_SECONDS
        self.timeout_seconds = int(os.environ.get("VISITOR_TIMEOUT_SECONDS", "30"))

        # Frame processing frequency to reduce compute: process every Nth frame
        # Set via env var FRAME_PROCESS_EVERY (default 1 = process all)
        self.process_every = max(1, int(os.environ.get("FRAME_PROCESS_EVERY", "1")))

        # ReID matching configuration (env-tunable)
        self.reid_sim_threshold = float(os.environ.get("REID_SIM_THRESHOLD", "0.62"))
        self.feature_avg_window = max(1, int(os.environ.get("FEATURE_AVG_WINDOW", "3")))
        self.min_crop_height = int(os.environ.get("MIN_CROP_HEIGHT", "80"))
        self.same_cam_continuity_seconds = int(os.environ.get("SAME_CAM_CONTINUITY_SECONDS", "5"))
        # Lightweight cosine-margin reranker
        self.reid_rerank_alpha = float(os.environ.get("REID_RERANK_ALPHA", "0.3"))  # weight for EMA similarity
        self.reid_rerank_margin = float(os.environ.get("REID_RERANK_MARGIN", "0.03"))  # min gap top vs second
        # Geometry gating (soft bonuses/penalties)
        self.geometry_config_path = os.environ.get("GEOMETRY_CONFIG_PATH", "")
        self.geometry_bonus = float(os.environ.get("GEOMETRY_GATING_WEIGHT", "0.05"))
        self.geometry_penalty = float(os.environ.get("GEOMETRY_PENALTY", "0.05"))
        self._adjacency = None  # lazy loaded
        # Cross-camera handoff relax rule
        self.handoff_window_seconds = int(os.environ.get("HANDOFF_WINDOW_SECONDS", "5"))
        self.handoff_margin = float(os.environ.get("HANDOFF_MARGIN", "0.03"))
        # Track last camera used for each global id
        self.last_camera_by_gid: Dict[str, str] = {}
        
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

        # Per-camera feature buffers for multi-frame averaging and last assignments
        self.feature_buffers: Dict[str, Dict[int, deque]] = {cid: defaultdict(lambda: deque(maxlen=self.feature_avg_window)) for cid in camera_sources}
        self.last_assignment: Dict[str, Dict[int, Dict[str, Any]]] = {cid: {} for cid in camera_sources}
        
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
        # Add 10% context padding around the bbox to stabilize embeddings
        x1, y1, x2, y2 = [int(v) for v in bbox]
        w = x2 - x1
        h = y2 - y1
        pad_x = int(0.1 * w)
        pad_y = int(0.1 * h)
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(frame.shape[1], x2 + pad_x)
        y2 = min(frame.shape[0], y2 + pad_y)
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

        # Frame skipping optimization: skip heavy processing on non-selected frames
        if self.process_every > 1 and (frame_num % self.process_every) != 0:
            # Optionally still dump raw frame counter for traceability
            # but skip detection/ReID to save compute
            return
        
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
        used_globals_this_frame: set[str] = set()
        for d in dets:
            # Same-camera continuity: if same local_id seen very recently, reuse
            prev = self.last_assignment[camera_id].get(d['local_id'])
            if prev is not None and (dt_now - prev['ts']).total_seconds() <= self.same_cam_continuity_seconds:
                global_id = prev['global_id']
                try:
                    mv = upsert_visitor(_mongo_db, global_id, dt_now, dt_now)
                    close_open_visit(_mongo_db, mv.get("_id"), dt_now)
                except Exception:
                    pass
                d["global_id"] = global_id
                self._log_reid_assignment(camera_id, frame_num, d['local_id'], global_id, is_new=False, similarity=1.0, timestamp=dt_now)
                self.last_assignment[camera_id][d['local_id']] = {"global_id": global_id, "ts": dt_now}
                processed_dets.append(d)
                continue

                # Extract crop; discard too-small crops to avoid noisy embeddings
                crop = self._extract_crop(frame_bgr, d["bbox"])
                if crop.size == 0 or crop.shape[0] < self.min_crop_height:
                    # Skip ReID; treat as no match to avoid false positives
                    match = None
                    emb_avg = None
                else:
                    emb = self.embedder.embed(crop)
                    # Attach current single-frame emb for StrongSortLite association
                    d["emb"] = emb
                    # Buffer features per local track and average
                    buf = self.feature_buffers[camera_id][d['local_id']]
                    buf.append(emb)
                    emb_avg = np.mean(np.stack(list(buf)), axis=0).astype(np.float32)
                    # Top-k candidate search with TTL filtering
                    topk = int(os.environ.get("REID_TOPK", "5"))
                    candidates = self.reid_index.search_topk(emb_avg, topk=topk, now_ts=dt_now.timestamp())
                    # Cosine-margin reranking against per-ID EMA feature
                    match = None
                    if candidates:
                        q = emb_avg / (np.linalg.norm(emb_avg) + 1e-8)
                        alpha = self.reid_rerank_alpha
                        scored = []
                        for gid, sim in candidates:
                            ema = self.reid_index.id_to_ema.get(gid)
                            sim_ema = float(np.dot(q, ema)) if ema is not None else sim
                            composite = (1.0 - alpha) * sim + alpha * sim_ema
                            # Apply soft geometry gating if available
                            composite += self._geometry_delta(camera_id, gid, dt_now)
                            scored.append((gid, sim, composite))
                        # sort by composite score desc
                        scored.sort(key=lambda x: x[2], reverse=True)
                        # apply per-frame uniqueness and thresholds with margin
                        top_gid, top_sim, top_score = scored[0]
                        second_score = scored[1][2] if len(scored) > 1 else -1.0
                        margin_ok = (top_score - second_score) >= self.reid_rerank_margin
                        if top_sim >= self.reid_sim_threshold and margin_ok and top_gid not in used_globals_this_frame:
                            match = (top_gid, top_sim)
                        else:
                            # Cross-camera handoff relax rule
                            prev_cam = self.last_camera_by_gid.get(top_gid)
                            if prev_cam and self._are_adjacent(prev_cam, camera_id):
                                # time-based gating using reid_index last seen
                                last_ts = self.reid_index.id_to_last_seen.get(top_gid, 0.0)
                                if (dt_now.timestamp() - last_ts) <= self.handoff_window_seconds:
                                    if (top_gid not in used_globals_this_frame) and (top_sim >= (self.reid_sim_threshold - self.handoff_margin)):
                                        match = (top_gid, top_sim)

                if match is None or (match is not None and match[1] < (self.reid_sim_threshold - self.handoff_margin)):
                    # New visitor detected
                    global_id = f"G{dt_now.timestamp():.0f}_{camera_id}_{d['local_id']}"
                    # If we have a valid averaged embedding, add to index
                    if emb_avg is not None:
                        self.reid_index.add(global_id, emb_avg, now_ts=dt_now.timestamp())
                    
                    # Log ReID assignment
                    self._log_reid_assignment(
                        camera_id, frame_num, d['local_id'], global_id, 
                        is_new=True, similarity=0.0, timestamp=dt_now
                    )
                    
                    try:
                        mv = upsert_visitor(_mongo_db, global_id, dt_now, dt_now)
                        insert_visit_event(_mongo_db, mv.get("_id"), camera_id, dt_now, global_id=global_id)
                    except Exception:
                        pass
                    
                    d["global_id"] = global_id
                    print(f"🆕 NEW visitor: {global_id} (cam={camera_id}, local_id={d['local_id']})")
                    # Cache assignment
                    self.last_assignment[camera_id][d['local_id']] = {"global_id": global_id, "ts": dt_now}
                    self.last_camera_by_gid[global_id] = camera_id
                else:
                    # Existing visitor - ReID match
                    global_id = match[0]
                    similarity = match[1]
                    
                    # Log ReID assignment
                    self._log_reid_assignment(
                        camera_id, frame_num, d['local_id'], global_id,
                        is_new=False, similarity=similarity, timestamp=dt_now
                    )
                    
                    try:
                        upsert_visitor(_mongo_db, global_id, dt_now, dt_now)
                    except Exception:
                        pass
                    
                    d["global_id"] = global_id
                    print(f"🔄 REID match: {global_id} (cam={camera_id}, local_id={d['local_id']}, sim={similarity:.3f})")
                    # Update index EMA and last_seen
                    if emb_avg is not None:
                        self.reid_index.update(global_id, emb_avg, now_ts=dt_now.timestamp())
                    # Reserve this global for this frame to prevent duplicates
                    used_globals_this_frame.add(global_id)
                    # Cache assignment
                    self.last_assignment[camera_id][d['local_id']] = {"global_id": global_id, "ts": dt_now}
                    self.last_camera_by_gid[global_id] = camera_id
                
                processed_dets.append(d)

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
        
        # Housekeeping: close timed-out visits (no sighting for timeout_seconds)
        self._close_timed_out_visits()

    def _load_geometry(self) -> None:
        if self._adjacency is not None:
            return
        if not self.geometry_config_path or not Path(self.geometry_config_path).exists():
            self._adjacency = {}
            return
        try:
            import json, yaml  # type: ignore
        except Exception:
            yaml = None
        try:
            text = Path(self.geometry_config_path).read_text()
            cfg = yaml.safe_load(text) if 'yaml' in (yaml.__name__ if yaml else '') else json.loads(text)
            self._adjacency = cfg.get('adjacency', {}) if isinstance(cfg, dict) else {}
        except Exception:
            self._adjacency = {}

    def _geometry_delta(self, current_cam: str, candidate_gid: str, now_ts: datetime) -> float:
        """Return a soft bonus/penalty based on camera adjacency.

        For phase 1, we only check if the last camera of the candidate is adjacent.
        """
        try:
            self._load_geometry()
            if not self._adjacency:
                return 0.0
            # Heuristic: parse last camera from global_id format G<ts>_<cam>_<local>
            parts = candidate_gid.split('_')
            prev_cam = parts[1] if len(parts) >= 3 else None
            if not prev_cam:
                return 0.0
            neighbors = set(self._adjacency.get(current_cam, []))
            if prev_cam in neighbors:
                return self.geometry_bonus
            else:
                return -self.geometry_penalty
        except Exception:
            return 0.0

    def _are_adjacent(self, cam_a: str, cam_b: str) -> bool:
        try:
            self._load_geometry()
            if not self._adjacency:
                return True  # if no config, do not block handoff
            neighbors = set(self._adjacency.get(cam_b, []))
            return cam_a in neighbors
        except Exception:
            return True
    
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

    def _close_timed_out_visits(self) -> None:
        """Mark visits as exited if their visitor hasn't been seen within timeout window."""
        cutoff = datetime.utcnow() - timedelta(seconds=self.timeout_seconds)
        try:
            # Close any open visit if last_seen is older than cutoff
            old_ids = [v["_id"] for v in _mongo_db.visitors.find({"last_seen_at": {"$lt": cutoff}}, {"_id": 1})]
            if old_ids:
                _mongo_db.visit_events.update_many({"visitor_id": {"$in": old_ids}, "out_time": None}, {"$set": {"out_time": datetime.utcnow()}})
        except Exception:
            pass


