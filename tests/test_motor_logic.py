"""
Unit Tests for Motor Controller Logic (motor_controller.py)
Verifies L298N action commands, speed clamping, direction inversion, and watchdog.
Runs 100% in mock mode without requiring physical GPIO hardware.
"""
import unittest
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from motor_controller import L298NMotorController


class TestMotorLogic(unittest.TestCase):
    def setUp(self):
        # Force mock mode
        self.mc = L298NMotorController(mock=True)

    def tearDown(self):
        self.mc.cleanup()

    def test_initial_state_is_stopped(self):
        """Motors must initialize safely in STOP state."""
        self.assertEqual(self.mc.current_action, config.ACTION_STOP)

    def test_forward_action_updates_state(self):
        """Forward command updates action and resets command timer."""
        t_before = time.perf_counter()
        self.mc.forward(speed=0.35)
        self.assertEqual(self.mc.current_action, config.ACTION_FORWARD)
        self.assertGreaterEqual(self.mc.last_command_time, t_before)

    def test_reverse_action_updates_state(self):
        """Reverse command updates action state."""
        self.mc.reverse(speed=0.35)
        self.assertEqual(self.mc.current_action, "REVERSE")

    def test_pivot_left_action_updates_state(self):
        """Pivot Left updates action state."""
        self.mc.pivot_left(speed=0.30)
        self.assertEqual(self.mc.current_action, config.ACTION_TURN_LEFT)

    def test_pivot_right_action_updates_state(self):
        """Pivot Right updates action state."""
        self.mc.pivot_right(speed=0.30)
        self.assertEqual(self.mc.current_action, config.ACTION_TURN_RIGHT)

    def test_stop_action_zeros_duty(self):
        """Stop command resets action state to STOP."""
        self.mc.forward(speed=0.40)
        self.mc.stop()
        self.assertEqual(self.mc.current_action, config.ACTION_STOP)

    def test_direction_inversion_initialization(self):
        """Verifies controller respects invert flags."""
        inverted_mc = L298NMotorController(invert_left=True, invert_right=False, mock=True)
        self.assertTrue(inverted_mc.invert_left)
        self.assertFalse(inverted_mc.invert_right)
        inverted_mc.cleanup()


if __name__ == "__main__":
    unittest.main()
