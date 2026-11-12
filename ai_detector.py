"""
AI Object Detection Module for Vision-Based Navigation Robot
Features:
- Modular BaseDetector interface allowing future plug-in of free-space segmentation or depth models.
- Local CPU inference via Ultralytics YOLO (supports YOLOv8n, YOLO11n, YOLO26n, or ONNX).
- Offline enforcement: Loads exclusively from local disk; no runtime cloud calls or downloads.
- Real-time HUD visualization with bounding boxes, labels, zones, and ground ROI line.
- Inference latency measurement (milliseconds) and rolling FPS counter.
"""
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import cv2

import config


@dataclass
class Detection:
    """Standardized representation of a detected visual object."""
    box: Tuple[int, int, int, int]  # (x1, y1, x2, y2) in pixel coordinates
    class_id: int
    label: str
    confidence: float
    center: Tuple[float, float]     # (cx, cy) normalized [0.0, 1.0]
    area_fraction: float            # box area divided by total frame area [0.0, 1.0]
    is_person: bool
    is_ground_hazard: bool          # True if bottom edge reaches the ground ROI


class BaseDetector(ABC):
    """Abstract perception interface for modular navigation backends."""

    @abstractmethod
    def detect(self, frame: np.ndarray) -> Tuple[List[Detection], float]:
        """
        Runs object detection on the input BGR image.
        Returns:
            (detections: List[Detection], inference_time_ms: float)
        """
        pass

    @abstractmethod
    def annotate(self, frame: np.ndarray, detections: List[Detection], action: str = "") -> np.ndarray:
        """Draws visual HUD overlay on the image."""
        pass


class YOLOv8Detector(BaseDetector):
    """
    Local CPU Object Detector using Ultralytics YOLO models (YOLOv8n / YOLO11n / YOLO26n).
    Operates strictly from local disk weights.
    """
    def __init__(
        self,
        model_path: str = config.MODEL_PATH,
        conf_thresh: float = config.CONFIDENCE_THRESHOLD,
        img_size: int = config.INFERENCE_IMAGE_SIZE
    ):
        self.model_path = model_path
        self.conf_thresh = conf_thresh
        self.img_size = img_size
        self.model = None
        self.class_names = {}
        self.fps_rolling = 0.0
        self.last_fps_time = time.perf_counter()

        self._load_local_model()

    def _load_local_model(self):
        """Verifies local weights exist and loads model onto CPU without internet."""
        print(f"[AI Detector] Loading pretrained model from: {self.model_path}")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"\n[AI Detector ERROR] Pretrained weights not found at: {self.model_path}\n"
                f"Please run the offline preparation script first:\n"
                f"    python download_model.py\n"
            )

        try:
            from ultralytics import YOLO
            # Explicitly load local weights onto CPU
            self.model = YOLO(self.model_path)
            self.class_names = self.model.names if hasattr(self.model, "names") else {}
            print(f"[AI Detector] Successfully loaded {len(self.class_names)} COCO classes onto CPU.")
        except Exception as e:
            raise RuntimeError(f"[AI Detector] Failed to initialize YOLO model: {e}")

    def detect(self, frame: np.ndarray) -> Tuple[List[Detection], float]:
        """
        Runs local inference on frame.
        Applies downsampling to INFERENCE_IMAGE_SIZE for high FPS on Pi 5 CPU.
        """
        if frame is None or self.model is None:
            return [], 0.0

        h, w = frame.shape[:2]
        t_start = time.perf_counter()

        # Run inference locally with CPU device
        # verbose=False prevents console clutter
        results = self.model.predict(
            source=frame,
            imgsz=self.img_size,
            conf=self.conf_thresh,
            device="cpu",
            verbose=False
        )

        t_end = time.perf_counter()
        inference_ms = (t_end - t_start) * 1000.0

        detections: List[Detection] = []
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                coords = box.xyxy[0].cpu().numpy().astype(int)
                x1, y1, x2, y2 = coords
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                label = self.class_names.get(cls_id, f"obj_{cls_id}")

                is_person = (label == "person")

                # Filter person detections using dedicated threshold
                if is_person and conf < config.PERSON_CONFIDENCE_THRESHOLD:
                    continue

                # Normalized coordinates and area
                cx = ((x1 + x2) / 2.0) / w
                cy = ((y1 + y2) / 2.0) / h
                box_area = max(0, x2 - x1) * max(0, y2 - y1)
                area_fraction = box_area / (w * h)

                # Check if bottom edge extends into ground ROI (closer to robot base)
                is_ground_hazard = (y2 / h) >= config.GROUND_ROI_Y_MIN

                detections.append(Detection(
                    box=(x1, y1, x2, y2),
                    class_id=cls_id,
                    label=label,
                    confidence=conf,
                    center=(cx, cy),
                    area_fraction=area_fraction,
                    is_person=is_person,
                    is_ground_hazard=is_ground_hazard
                ))

        return detections, inference_ms

    def annotate(self, frame: np.ndarray, detections: List[Detection], action: str = "") -> np.ndarray:
        """
        Overlays bounding boxes, navigation zones (Left/Center/Right), ground ROI line,
        and current robot action banner.
        """
        vis = frame.copy()
        h, w = vis.shape[:2]

        # 1. Draw Navigation Zone Dividers (Dashed / semi-transparent)
        zl_x = int(w * config.ZONE_LEFT_END)
        zr_x = int(w * config.ZONE_RIGHT_START)
        roi_y = int(h * config.GROUND_ROI_Y_MIN)

        # Ground ROI horizontal line
        cv2.line(vis, (0, roi_y), (w, roi_y), (100, 100, 100), 1, cv2.LINE_AA)
        cv2.putText(vis, "GROUND ROI", (10, roi_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1)

        # Zone vertical boundaries
        cv2.line(vis, (zl_x, roi_y), (zl_x, h), (255, 255, 0), 1, cv2.LINE_AA)
        cv2.line(vis, (zr_x, roi_y), (zr_x, h), (255, 255, 0), 1, cv2.LINE_AA)

        # Zone labels
        cv2.putText(vis, "LEFT", (int(zl_x / 2) - 15, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
        cv2.putText(vis, "CENTER", (int((zl_x + zr_x) / 2) - 25, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
        cv2.putText(vis, "RIGHT", (int((zr_x + w) / 2) - 20, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

        # 2. Draw Object Detections
        for det in detections:
            x1, y1, x2, y2 = det.box

            # Red box for persons, Orange for ground hazards, Green for background
            if det.is_person:
                color = (0, 0, 255) # Red for person
                tag = f"PERSON ({det.confidence*100:.0f}%)"
            elif det.label in config.HAZARD_CLASSES:
                color = (0, 140, 255) # Orange for obstacle hazard
                tag = f"{det.label} ({det.confidence*100:.0f}%)"
            else:
                color = (0, 220, 0)
                tag = f"{det.label} ({det.confidence*100:.0f}%)"

            # Draw box and label banner
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            cv2.rectangle(vis, (x1, max(0, y1 - 20)), (x1 + len(tag) * 8 + 8, y1), color, -1)
            cv2.putText(vis, tag, (x1 + 4, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # 3. Draw Robot Action Banner at Top
        action_colors = {
            config.ACTION_FORWARD: (0, 200, 0),     # Green
            config.ACTION_TURN_LEFT: (255, 180, 0), # Blue-Yellow
            config.ACTION_TURN_RIGHT: (255, 180, 0),
            config.ACTION_STOP: (0, 0, 255)         # Red
        }
        color_act = action_colors.get(action, (200, 200, 200))
        cv2.rectangle(vis, (0, 0), (w, 36), (20, 20, 25), -1)
        cv2.putText(vis, f"ACTION: {action}", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_act, 2)

        return vis


class MockDetector(BaseDetector):
    """
    Synthetic detector that returns programmable detections for unit testing without weights.
    """
    def __init__(self, predefined_detections: Optional[List[Detection]] = None):
        self.predefined_detections = predefined_detections or []

    def set_detections(self, detections: List[Detection]):
        self.predefined_detections = detections

    def detect(self, frame: np.ndarray) -> Tuple[List[Detection], float]:
        return self.predefined_detections, 1.5

    def annotate(self, frame: np.ndarray, detections: List[Detection], action: str = "") -> np.ndarray:
        return frame.copy()


if __name__ == "__main__":
    print("[AI Detector] Verifying local model...")
    try:
        det = YOLOv8Detector()
        dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
        dets, ms = det.detect(dummy_img)
        print(f"[AI Detector] Warm-up inference successful! Latency: {ms:.1f}ms, Detections: {len(dets)}")
    except Exception as e:
        print(f"[AI Detector] Error during verification: {e}")
