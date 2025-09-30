from typing import List, Dict, Any, Tuple
import numpy as np


def _iou(boxA: List[float], boxB: List[float]) -> float:
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    boxAArea = max(0, (boxA[2] - boxA[0])) * max(0, (boxA[3] - boxA[1]))
    boxBArea = max(0, (boxB[2] - boxB[0])) * max(0, (boxB[3] - boxB[1]))
    denom = boxAArea + boxBArea - interArea + 1e-8
    return float(interArea / denom) if denom > 0 else 0.0


class SimpleTracker:
    """
    Minimal IOU-based tracker stub that assigns incremental local IDs.
    Replace with DeepSORT/ByteTrack integration later.
    """

    def __init__(self) -> None:
        self.next_id = 1

    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for d in detections:
            if "local_id" not in d:
                d["local_id"] = self.next_id
                self.next_id += 1
        return detections


class StrongSortLite:
    """A lightweight StrongSORT-like tracker combining IoU and appearance.

    Notes:
    - Maintains tracks with last bbox, last embedding and local_id.
    - Associates using a cost that blends IoU (1 - IoU) and appearance (1 - cosine).
    - Uses Hungarian algorithm via scipy if available; otherwise greedy matching.
    """

    def __init__(self, appearance_weight: float = 0.6, iou_weight: float = 0.4) -> None:
        self.next_id = 1
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.appearance_weight = float(appearance_weight)
        self.iou_weight = float(iou_weight)
        try:
            from scipy.optimize import linear_sum_assignment  # type: ignore
            self._hungarian = linear_sum_assignment
        except Exception:
            self._hungarian = None

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        da = float(np.linalg.norm(a))
        db = float(np.linalg.norm(b))
        if da == 0 or db == 0:
            return 0.0
        return float(np.dot(a, b) / (da * db))

    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Prepare cost matrix between current tracks and detections
        track_ids = list(self.tracks.keys())
        T = len(track_ids)
        D = len(detections)
        if T == 0:
            # Initialize new tracks
            for d in detections:
                d["local_id"] = self.next_id
                self.tracks[self.next_id] = {
                    "bbox": d["bbox"],
                    "emb": np.array(d.get("emb", []), dtype=np.float32) if "emb" in d else None,
                }
                self.next_id += 1
            return detections

        cost = np.ones((T, D), dtype=np.float32)
        for ti, tid in enumerate(track_ids):
            tb = self.tracks[tid]["bbox"]
            te = self.tracks[tid].get("emb")
            for dj, det in enumerate(detections):
                iou = _iou(tb, det["bbox"])  # higher is better
                app = 0.0
                de = det.get("emb")
                if te is not None and de is not None:
                    app = self._cosine(te, np.array(de, dtype=np.float32))  # higher is better
                # Convert to cost (lower is better)
                cost[ti, dj] = self.iou_weight * (1.0 - iou) + self.appearance_weight * (1.0 - app)

        # Solve assignment
        assignments: List[Tuple[int, int]] = []
        assigned_dets = set()
        assigned_trks = set()
        if self._hungarian is not None:
            row_ind, col_ind = self._hungarian(cost)
            for r, c in zip(row_ind, col_ind):
                assignments.append((r, c))
                assigned_trks.add(r)
                assigned_dets.add(c)
        else:
            # Greedy fallback
            for _ in range(min(T, D)):
                ti, dj = divmod(np.argmin(cost), D)
                if ti in assigned_trks or dj in assigned_dets:
                    cost[ti, dj] = np.inf
                    continue
                assignments.append((ti, dj))
                assigned_trks.add(ti)
                assigned_dets.add(dj)
                cost[ti, :] = np.inf
                cost[:, dj] = np.inf

        # Update assigned
        for ti, dj in assignments:
            tid = track_ids[ti]
            detections[dj]["local_id"] = tid
            self.tracks[tid]["bbox"] = detections[dj]["bbox"]
            if "emb" in detections[dj]:
                self.tracks[tid]["emb"] = np.array(detections[dj]["emb"], dtype=np.float32)

        # New tracks for unassigned detections
        for dj, det in enumerate(detections):
            if dj in assigned_dets:
                continue
            det["local_id"] = self.next_id
            self.tracks[self.next_id] = {
                "bbox": det["bbox"],
                "emb": np.array(det.get("emb", []), dtype=np.float32) if "emb" in det else None,
            }
            self.next_id += 1

        return detections


