"""
Camera Module for AI Vision-Based Navigation Robot
Features:
- Threaded background frame capture to drain OpenCV/V4L2 hardware buffers
  (eliminates stale frame latency).
- High-precision timestamping and stale-frame health monitoring.
- Robust index fallback and failure detection.
- Built-in Mock Camera fallback for offline development and laptop testing.
"""
import time
import threading
from typing import Tuple, Optional
import numpy as np
import cv2

import config


class USBCamera:
    """
    Manages USB webcam video capture on Raspberry Pi 5.
    Runs a background daemon thread to constantly read frames so that
    calls to `get_frame()` always receive the freshest possible image.
    """
    def __init__(
        self,
        device_index: int = config.CAMERA_DEVICE_INDEX,
        width: int = config.FRAME_WIDTH,
        height: int = config.FRAME_HEIGHT,
        fps: int = config.CAMERA_FPS,
        mock: bool = False
    ):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.mock = mock

        self.cap: Optional[cv2.VideoCapture] = None
        self.latest_frame: Optional[np.ndarray] = None
        self.last_frame_time: float = 0.0
        self.is_running: bool = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        if not self.mock:
            self._init_hardware()
        else:
            self._init_mock()

    def _init_hardware(self):
        """Attempts to open physical webcam device."""
        print(f"[Camera] Initializing USB Webcam (index {self.device_index}, {self.width}x{self.height})...")
        self.cap = cv2.VideoCapture(self.device_index)

        # On Linux / Raspberry Pi OS, V4L2 backend is preferred
        if not self.cap.isOpened():
            # Try index 1 or direct device node
            print(f"[Camera] Warning: Failed to open index {self.device_index}. Trying fallback index 1...")
            self.cap = cv2.VideoCapture(1)

        if not self.cap.isOpened():
            print("[Camera] Warning: No physical USB webcam detected. Switching to Mock Camera mode.")
            self.mock = True
            self._init_mock()
            return

        # Configure hardware parameters
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        # Read test frame to verify sensor stream
        ret, frame = self.cap.read()
        if not ret or frame is None:
            print("[Camera] Warning: Opened device but failed to read initial frame. Falling back to Mock.")
            self.mock = True
            self._init_mock()
            return

        with self.lock:
            self.latest_frame = frame
            self.last_frame_time = time.perf_counter()

        self.is_running = True
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()
        print("[Camera] USB Webcam successfully started with buffer-draining thread.")

    def _init_mock(self):
        """Initializes synthetic mock stream for laptop testing."""
        print("[Camera] Running in Synthetic Mock Camera mode (no hardware required).")
        self.is_running = True
        self.latest_frame = self._generate_mock_frame(0)
        self.last_frame_time = time.perf_counter()
        self.thread = threading.Thread(target=self._mock_worker, daemon=True)
        self.thread.start()

    def _capture_worker(self):
        """Continuously reads frames from hardware to keep buffer completely flushed."""
        while self.is_running:
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.lock:
                        self.latest_frame = frame
                        self.last_frame_time = time.perf_counter()
                else:
                    time.sleep(0.02)
            else:
                time.sleep(0.05)

    def _mock_worker(self):
        """Generates continuous animated mock indoor frames at target FPS."""
        frame_idx = 0
        interval = 1.0 / self.fps
        while self.is_running:
            frame = self._generate_mock_frame(frame_idx)
            with self.lock:
                self.latest_frame = frame
                self.last_frame_time = time.perf_counter()
            frame_idx += 1
            time.sleep(interval)

    def _generate_mock_frame(self, step: int) -> np.ndarray:
        """Draws a synthetic indoor corridor floor with moving mock objects."""
        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Wall (top)
        canvas[0:180, :] = [60, 65, 75]
        # Floor (bottom)
        canvas[180:, :] = [140, 150, 160]

        # Floor horizon line
        cv2.line(canvas, (0, 180), (self.width, 180), (40, 45, 55), 2)

        # Draw a synthetic chair/box obstacle in center
        cx = int(self.width / 2 + 50 * np.sin(step * 0.05))
        cy = 320
        cv2.rectangle(canvas, (cx - 40, cy - 60), (cx + 40, cy + 40), (40, 90, 180), -1)
        cv2.putText(canvas, "MOCK OBSTACLE", (cx - 50, cy - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        cv2.putText(canvas, f"MOCK CAMERA FEED [Frame {step}]", (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        return canvas

    def get_frame(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Retrieves the latest captured frame and performs safety health checks.
        Returns:
            (is_valid: bool, frame: Optional[np.ndarray], frame_age_seconds: float)
        """
        with self.lock:
            if self.latest_frame is None:
                return False, None, 999.0

            frame_copy = self.latest_frame.copy()
            frame_age = time.perf_counter() - self.last_frame_time

        # Stale frame check: If hardware freezes or camera drops, mark as invalid!
        if frame_age > config.FRAME_TIMEOUT_S:
            return False, frame_copy, frame_age

        return True, frame_copy, frame_age

    def release(self):
        """Gracefully terminates capture thread and closes video device."""
        self.is_running = False
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        print("[Camera] Camera resources successfully released.")


if __name__ == "__main__":
    print("[Camera] Running standalone camera test...")
    cam = USBCamera()
    try:
        for i in range(10):
            success, frame, age = cam.get_frame()
            print(f"Sample {i+1}: Success={success} | Shape={frame.shape if frame is not None else None} | Age={age*1000:.1f}ms")
            time.sleep(0.1)
    finally:
        cam.release()
