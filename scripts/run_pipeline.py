#!/usr/bin/env python3
import cv2
from core.pipeline.multicam import MultiCameraOrchestrator


def main() -> None:
    # Example sources; replace with RTSP/HTTP files as needed
    cameras = {
        "cam1": "/app/data/test_video_1.mp4",
        "cam2": "/app/data/test_video_2.mp4",
    }

    orchestrator = MultiCameraOrchestrator(cameras)

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


