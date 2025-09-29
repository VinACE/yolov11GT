from typing import List, Dict, Any


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


