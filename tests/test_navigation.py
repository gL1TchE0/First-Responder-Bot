"""
Unit Tests for Reactive Navigation Engine (navigation.py)
Verifies spatial zone reasoning, human safety overrides, and fail-safe handling.
Requires ZERO hardware; runs completely offline and deterministically.
"""
import unittest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from ai_detector import Detection
from navigation import ReactiveNavigator, NavigationDecision


def make_detection(
    label: str,
    cx: float,
    cy: float,
    area_fraction: float,
    confidence: float = 0.85,
    is_person: bool = False,
    is_ground: bool = True
) -> Detection:
    """Helper to synthesize test detections with precise spatial coordinates."""
    w_px, h_px = 640, 480
    box_w = int(w_px * (area_fraction ** 0.5))
    box_h = int(h_px * (area_fraction ** 0.5))
    x1 = int(cx * w_px - box_w / 2)
    y1 = int(cy * h_px - box_h / 2)
    x2 = x1 + box_w
    y2 = y1 + box_h

    return Detection(
        box=(x1, y1, x2, y2),
        class_id=0 if is_person else 1,
        label=label,
        confidence=confidence,
        center=(cx, cy),
        area_fraction=area_fraction,
        is_person=is_person,
        is_ground_hazard=is_ground
    )


class TestReactiveNavigator(unittest.TestCase):
    def setUp(self):
        self.nav = ReactiveNavigator()

    def test_clear_corridor_forward(self):
        """When no hazards are present, forward motion must be permitted."""
        dec = self.nav.evaluate(camera_ok=True, frame_age=0.03, detections=[])
        self.assertEqual(dec.action, config.ACTION_FORWARD)
        self.assertFalse(dec.is_emergency)
        self.assertIn("CLEAR CORRIDOR", dec.reason)

    def test_center_obstacle_turns_to_clear_left(self):
        """When center is blocked and left side has open clearance, turn left."""
        # Obstacle in center (cx=0.50, area=0.20)
        center_box = make_detection("box", cx=0.50, cy=0.60, area_fraction=0.20)
        # Right side slightly occupied (cx=0.80, area=0.10)
        right_box = make_detection("chair", cx=0.80, cy=0.60, area_fraction=0.10)

        dec = self.nav.evaluate(camera_ok=True, frame_age=0.03, detections=[center_box, right_box])
        self.assertEqual(dec.action, config.ACTION_TURN_LEFT)
        self.assertIn("Left opening clearer", dec.reason)

    def test_center_obstacle_turns_to_clear_right(self):
        """When center is blocked and right side has open clearance, turn right."""
        # Obstacle in center (cx=0.50, area=0.20)
        center_box = make_detection("box", cx=0.50, cy=0.60, area_fraction=0.20)
        # Left side occupied (cx=0.20, area=0.15)
        left_box = make_detection("chair", cx=0.20, cy=0.60, area_fraction=0.15)

        dec = self.nav.evaluate(camera_ok=True, frame_age=0.03, detections=[center_box, left_box])
        self.assertEqual(dec.action, config.ACTION_TURN_RIGHT)
        self.assertIn("Right opening clearer", dec.reason)

    def test_all_paths_blocked_stops(self):
        """When Center, Left, and Right are all obstructed, stop safely."""
        center_obs = make_detection("couch", cx=0.50, cy=0.60, area_fraction=0.25)
        left_obs = make_detection("chair", cx=0.15, cy=0.60, area_fraction=0.25)
        right_obs = make_detection("dining table", cx=0.85, cy=0.60, area_fraction=0.25)

        dec = self.nav.evaluate(camera_ok=True, frame_age=0.03, detections=[center_obs, left_obs, right_obs])
        self.assertEqual(dec.action, config.ACTION_STOP)
        self.assertIn("ALL PATHS BLOCKED", dec.reason)

    def test_person_in_center_triggers_human_safety_stop(self):
        """A person in the center zone must trigger immediate emergency stop."""
        person = make_detection("person", cx=0.50, cy=0.60, area_fraction=0.12, is_person=True)

        dec = self.nav.evaluate(camera_ok=True, frame_age=0.03, detections=[person])
        self.assertEqual(dec.action, config.ACTION_STOP)
        self.assertTrue(dec.is_emergency)
        self.assertIn("HUMAN SAFETY PROTOCOL", dec.reason)

    def test_person_on_left_veers_right(self):
        """Robot must never approach a person; veer right if person is on left."""
        person_left = make_detection("person", cx=0.20, cy=0.60, area_fraction=0.10, is_person=True)

        dec = self.nav.evaluate(camera_ok=True, frame_age=0.03, detections=[person_left])
        self.assertEqual(dec.action, config.ACTION_TURN_RIGHT)
        self.assertIn("Turning away from person", dec.reason)

    def test_stale_camera_frame_triggers_fail_safe_stop(self):
        """If frame age exceeds safety timeout, robot must halt immediately."""
        # Frame age = 1.2 seconds (> FRAME_TIMEOUT_S 0.8s)
        dec = self.nav.evaluate(camera_ok=True, frame_age=1.2, detections=[])
        self.assertEqual(dec.action, config.ACTION_STOP)
        self.assertTrue(dec.is_emergency)
        self.assertIn("FAIL-SAFE", dec.reason)

    def test_camera_offline_triggers_fail_safe_stop(self):
        """If camera signal is dropped, robot must halt immediately."""
        dec = self.nav.evaluate(camera_ok=False, frame_age=0.01, detections=[])
        self.assertEqual(dec.action, config.ACTION_STOP)
        self.assertTrue(dec.is_emergency)
        self.assertIn("FAIL-SAFE", dec.reason)

    def test_inference_failure_triggers_fail_safe_stop(self):
        """If AI inference throws an exception, robot must halt immediately."""
        dec = self.nav.evaluate(camera_ok=True, frame_age=0.03, detections=[], inference_ok=False)
        self.assertEqual(dec.action, config.ACTION_STOP)
        self.assertTrue(dec.is_emergency)
        self.assertIn("AI object detector inference error", dec.reason)

    def test_background_ceiling_objects_ignored(self):
        """Objects in the upper background (e.g., ceiling lights) do not trigger floor stops."""
        # Non-ground object (cy=0.15, is_ground=False)
        ceiling_lamp = make_detection("tv", cx=0.50, cy=0.15, area_fraction=0.25, is_ground=False)

        dec = self.nav.evaluate(camera_ok=True, frame_age=0.03, detections=[ceiling_lamp])
        self.assertEqual(dec.action, config.ACTION_FORWARD)


if __name__ == "__main__":
    unittest.main()
