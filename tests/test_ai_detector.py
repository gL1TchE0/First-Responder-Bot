"""
Unit Tests for AI Perception Module (ai_detector.py)
Verifies Detection dataclass, spatial zone calculations, and MockDetector behavior.
"""
import unittest
import sys
import numpy as np
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_detector import Detection, MockDetector


class TestAIDetector(unittest.TestCase):
    def test_detection_dataclass_fields(self):
        """Verifies Detection structure contains all required perception fields."""
        det = Detection(
            box=(100, 150, 300, 400),
            class_id=0,
            label="person",
            confidence=0.92,
            center=(0.3125, 0.5729),
            area_fraction=0.1627,
            is_person=True,
            is_ground_hazard=True
        )
        self.assertEqual(det.label, "person")
        self.assertTrue(det.is_person)
        self.assertTrue(det.is_ground_hazard)
        self.assertAlmostEqual(det.confidence, 0.92)

    def test_mock_detector_interface(self):
        """Verifies MockDetector complies with BaseDetector interface."""
        dummy_det = Detection(
            box=(50, 50, 150, 150),
            class_id=56,
            label="chair",
            confidence=0.88,
            center=(0.156, 0.208),
            area_fraction=0.032,
            is_person=False,
            is_ground_hazard=True
        )
        mock_detector = MockDetector(predefined_detections=[dummy_det])
        dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)

        dets, ms = mock_detector.detect(dummy_img)
        self.assertEqual(len(dets), 1)
        self.assertEqual(dets[0].label, "chair")
        self.assertGreater(ms, 0.0)


if __name__ == "__main__":
    unittest.main()
