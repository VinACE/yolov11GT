#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cv2
from core.pipeline.multicam import MultiCameraOrchestrator


def main() -> None:
    # Example sources; replace with RTSP/HTTP files as needed
    cameras = {
        "cam1": "/app/data/demo3.mp4",
        "cam2": "/app/data/demo3.mp4",
    }

    # Initialize with OSNet ReID for production (set use_osnet=False to use stub)
    orchestrator = MultiCameraOrchestrator(cameras, use_osnet=True)

    caps = {cid: cv2.VideoCapture(src) for cid, src in cameras.items()}
    try:
        while True:
            for cid, cap in caps.items():
                ok, frame = cap.read()
                if not ok:
                    continue
                orchestrator.process_frame(cid, frame)
    finally:
        for cap in caps.values():
            cap.release()


if __name__ == "__main__":
    main()


