"""
Main Application Orchestrator for Offline AI Vision-Based Navigation Robot
Coordinates Camera Acquisition -> Local YOLO Perception -> Reactive Spatial Reasoning -> L298N Drive
Features:
- Completely offline execution (no cloud calls, no weights downloading at runtime).
- Strict startup safety checklist: Motors remain disabled until camera and AI model are verified.
- Real-time diagnostic telemetry: Loop FPS, inference latency (ms), CPU utilization %, action reasoning.
- Dual interface: Headless console mode (for SSH) or Live OpenCV visual HUD window.
- Fail-safe exception handler with guaranteed motor shutdown.
"""
import os
import sys
import time
import signal
import argparse
import psutil
import cv2

# Ensure clean UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
from camera import USBCamera
from ai_detector import YOLOv8Detector
from navigation import ReactiveNavigator, NavigationDecision
from motor_controller import L298NMotorController


class AINavigationRobot:
    def __init__(self, headless: bool = False, mock_hw: bool = False):
        self.headless = headless
        self.mock_hw = mock_hw
        self.is_running = True

        print("=" * 70)
        print("🤖 OFFLINE AI VISION NAVIGATION ROBOT - STARTUP SEQUENCE")
        print("Platform: Raspberry Pi 5 | Model: " + config.MODEL_NAME)
        print("Mode: " + ("HEADLESS (Console)" if self.headless else "GUI (OpenCV HUD Window)"))
        print("=" * 70)

        # Step 1: Initialize Camera
        print("\n[Startup 1/4] Initializing USB Webcam Stream...")
        self.camera = USBCamera(mock=self.mock_hw)

        # Step 2: Initialize AI Detector locally
        print("\n[Startup 2/4] Initializing Local AI Object Detector...")
        self.detector = YOLOv8Detector(model_path=config.MODEL_PATH)

        # Step 3: Initialize Reactive Navigator
        print("\n[Startup 3/4] Initializing Reactive Spatial Navigator...")
        self.navigator = ReactiveNavigator()

        # Step 4: Initialize Motor Controller (Starts in STOP state)
        print("\n[Startup 4/4] Initializing L298N Motor Driver...")
        self.motors = L298NMotorController(mock=self.mock_hw)

        print("\n" + "=" * 70)
        print("✅ ALL SUBSYSTEMS VERIFIED. ROBOT READY FOR AUTONOMOUS RUN.")
        print("Press Ctrl+C or 'q' in the GUI window to stop.")
        print("=" * 70 + "\n")

        # Setup OS signal handlers for clean emergency stop
        signal.signal(signal.SIGINT, self._sig_handler)
        signal.signal(signal.SIGTERM, self._sig_handler)

    def _sig_handler(self, sig, frame):
        print("\n[System] Shutdown signal received! Stopping robot safely...")
        self.is_running = False

    def run(self, max_steps: int = 0):
        step_count = 0
        fps_counter = 0
        t_fps_start = time.perf_counter()
        current_fps = 0.0
        process = psutil.Process()

        try:
            while self.is_running:
                t_step_start = time.perf_counter()
                step_count += 1

                # 1. Capture Camera Frame & Check Stale Age
                cam_ok, frame, frame_age = self.camera.get_frame()

                # 2. Run Local AI Inference
                inference_ok = False
                detections = []
                infer_ms = 0.0

                if cam_ok and frame is not None:
                    try:
                        detections, infer_ms = self.detector.detect(frame)
                        inference_ok = True
                    except Exception as e:
                        print(f"[Perception ERROR] Detection failed: {e}")
                        inference_ok = False

                # 3. Evaluate Reactive Spatial Navigation Policy
                decision: NavigationDecision = self.navigator.evaluate(
                    camera_ok=cam_ok,
                    frame_age=frame_age,
                    detections=detections,
                    inference_ok=inference_ok
                )

                # 4. Command L298N Motor Drivers
                self._execute_motor_action(decision.action)

                # 5. Measure Loop Timing and Telemetry
                t_step_end = time.perf_counter()
                fps_counter += 1
                if t_step_end - t_fps_start >= 1.0:
                    current_fps = fps_counter / (t_step_end - t_fps_start)
                    fps_counter = 0
                    t_fps_start = t_step_end

                cpu_pct = process.cpu_percent()

                # Print periodic console diagnostics
                if step_count % 3 == 0 or decision.is_emergency:
                    det_summary = ", ".join([f"{d.label}({d.confidence*100:.0f}%)" for d in detections[:3]]) or "None"
                    print(
                        f"Step {step_count:04d} | "
                        f"Action: {decision.action:10s} | "
                        f"Infer: {infer_ms:4.1f}ms | "
                        f"FPS: {current_fps:4.1f} | "
                        f"CPU: {cpu_pct:4.1f}% | "
                        f"Risks [L:{decision.zone_risks.get('left',0):.2f} C:{decision.zone_risks.get('center',0):.2f} R:{decision.zone_risks.get('right',0):.2f}] | "
                        f"Obs: {det_summary}"
                    )
                    if decision.is_emergency:
                        print(f"  -> REASON: {decision.reason}")

                # 6. Render GUI HUD Window if enabled
                if not self.headless and frame is not None:
                    hud_frame = self.detector.annotate(frame, detections, action=decision.action)

                    # Add telemetry banner
                    cv2.putText(
                        hud_frame,
                        f"Infer: {infer_ms:.1f}ms | FPS: {current_fps:.1f} | CPU: {cpu_pct:.1f}%",
                        (10, hud_frame.shape[0] - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1
                    )
                    cv2.imshow("Raspberry Pi 5 AI Navigation HUD", hud_frame)

                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27: # 'q' or ESC
                        print("\n[GUI] 'q' pressed. Initiating graceful shutdown...")
                        self.is_running = False
                    elif key == ord(' '): # Spacebar manual emergency stop
                        print("\n[GUI] MANUAL EMERGENCY STOP PRESSED!")
                        self.motors.stop(reason="MANUAL_E_STOP")
                        time.sleep(1.0)

                # Check max steps limit (for automated tests)
                if max_steps > 0 and step_count >= max_steps:
                    print(f"[Main] Reached requested step count limit ({max_steps}). Exiting.")
                    break

                # Sleep small remainder to maintain target loop cadence
                elapsed = time.perf_counter() - t_step_start
                target_period = 1.0 / config.CAMERA_FPS
                if elapsed < target_period:
                    time.sleep(target_period - elapsed)

        finally:
            self._shutdown()

    def _execute_motor_action(self, action: str):
        """Dispatches navigation action to the L298N driver with conservative speed limits."""
        if action == config.ACTION_FORWARD:
            self.motors.forward(speed=config.SPEED_FORWARD)
        elif action == config.ACTION_TURN_LEFT:
            self.motors.pivot_left(speed=config.SPEED_TURN)
        elif action == config.ACTION_TURN_RIGHT:
            self.motors.pivot_right(speed=config.SPEED_TURN)
        else:
            self.motors.stop(reason="NAVIGATION_DECISION")

    def _shutdown(self):
        """Ensures motors are completely de-energized and camera handles are closed."""
        print("\n[Shutdown] Executing safe teardown sequence...")
        if hasattr(self, "motors") and self.motors is not None:
            self.motors.stop(reason="SYSTEM_SHUTDOWN")
            self.motors.cleanup()
        if hasattr(self, "camera") and self.camera is not None:
            self.camera.release()
        if not self.headless:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        print("[Shutdown] Robot safe shutdown complete.")


def main():
    parser = argparse.ArgumentParser(description="Offline AI Vision-Based Navigation Robot for Raspberry Pi 5")
    parser.add_argument("--headless", action="store_true", help="Run without graphical display window (SSH mode)")
    parser.add_argument("--mock", action="store_true", help="Force synthetic mock camera and mock GPIO")
    parser.add_argument("--steps", type=int, default=0, help="Run for N steps then exit (useful for automated benchmarks)")
    args = parser.parse_args()

    robot = AINavigationRobot(headless=args.headless, mock_hw=args.mock)
    robot.run(max_steps=args.steps)


if __name__ == "__main__":
    main()
