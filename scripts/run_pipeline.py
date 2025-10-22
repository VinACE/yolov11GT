#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cv2
from core.pipeline.multicam import MultiCameraOrchestrator


def main() -> None:
    # Example sources; replace with RTSP/HTTP files as needed
    # NOTE: Sample.mp4 and SampleGT.mp4 are IDENTICAL videos (same MD5)
    # Using all 3 to simulate real multi-camera environment
    # ReID should match same people across cam2 and cam3 since they're identical
    # Expected unique count: 11-12 people (cam2 & cam3 should merge to same IDs)
    cameras = {
        "cam1": "/app/data/demo3.mp4",
        "cam2": "/app/data/Sample.mp4",
        "cam3": "/app/data/SampleGT.mp4",
        "cam4": "/app/data/demo3.mp4"
    }

    # Initialize with OSNet ReID for production (set use_osnet=False to use stub)
    orchestrator = MultiCameraOrchestrator(cameras, use_osnet=True)

    caps = {cid: cv2.VideoCapture(src) for cid, src in cameras.items()}
    
    # Track which cameras have finished (reached end of video)
    finished_cameras = set()
    
    try:
        while len(finished_cameras) < len(cameras):
            for cid, cap in caps.items():
                if cid in finished_cameras:
                    continue
                    
                ok, frame = cap.read()
                if not ok:
                    # Video ended - mark as finished
                    print(f"📹 Camera {cid} finished processing video")
                    finished_cameras.add(cid)
                    continue
                    
                orchestrator.process_frame(cid, frame)
        
        print(f"\n✅ All {len(cameras)} cameras finished processing!")
        print(f"📊 Final statistics:")
        print(f"   Total frames: {sum(orchestrator.frame_count.values())}")
        print(f"   Unique visitors: {len(orchestrator.reid_index.id_to_ema)}")
        print(f"   ReID database size: {len(orchestrator.reid_index.global_ids)}")
        
    finally:
        for cap in caps.values():
            cap.release()


if __name__ == "__main__":
    main()


