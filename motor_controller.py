"""
L298N Dual H-Bridge Motor Controller for Raspberry Pi 5
Platform: Raspberry Pi 5 (8GB) | OS: Raspberry Pi OS Bookworm | Backend: gpiozero / lgpio

Hardware Details:
- 1x L298N Dual Full H-Bridge Module:
  * Motor A (OUT1, OUT2): Left side DC motors in parallel.
  * Motor B (OUT3, OUT4): Right side DC motors in parallel.
- BCM Pin Assignment:
  * Left: ENA (GPIO 12 PWM, Pin 32), IN1 (GPIO 17, Pin 11), IN2 (GPIO 27, Pin 13)
  * Right: ENB (GPIO 13 PWM, Pin 33), IN3 (GPIO 22, Pin 15), IN4 (GPIO 23, Pin 16)
- Features:
  * Direction inversion toggles for Left and Right tracks.
  * Software speed limit cap (MAX_SPEED_DUTY = 0.50).
  * Watchdog safety stop if commands stall.
  * Automatic Mock Fallback for off-Pi testing.
"""
import time
import threading
from typing import Optional
import config

HAS_HARDWARE_GPIO = False
try:
    from gpiozero import PWMOutputDevice, DigitalOutputDevice
    HAS_HARDWARE_GPIO = True
except (ImportError, Exception):
    HAS_HARDWARE_GPIO = False


class L298NMotorController:
    """
    Manages 4WD skid-steer chassis via an L298N dual H-bridge motor driver.
    """
    def __init__(
        self,
        ena_pin: int = config.PIN_L298N_ENA,
        in1_pin: int = config.PIN_L298N_IN1,
        in2_pin: int = config.PIN_L298N_IN2,
        enb_pin: int = config.PIN_L298N_ENB,
        in3_pin: int = config.PIN_L298N_IN3,
        in4_pin: int = config.PIN_L298N_IN4,
        invert_left: bool = config.MOTOR_INVERT_LEFT,
        invert_right: bool = config.MOTOR_INVERT_RIGHT,
        mock: bool = False
    ):
        self.ena_pin = ena_pin
        self.in1_pin = in1_pin
        self.in2_pin = in2_pin
        self.enb_pin = enb_pin
        self.in3_pin = in3_pin
        self.in4_pin = in4_pin
        self.invert_left = invert_left
        self.invert_right = invert_right
        self.mock = mock or (not HAS_HARDWARE_GPIO)

        self.current_action = config.ACTION_STOP
        self.last_command_time = time.perf_counter()
        self.is_running = True

        if not self.mock:
            self._init_gpio()
        else:
            print("[Motors] Running in Mock Motor Controller mode (no hardware required).")

        # Start watchdog safety monitor
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def _init_gpio(self):
        """Initializes gpiozero hardware PWM devices for 2x L298N drivers (4 independent motors)."""
        print(f"[Motors] Initializing 2x L298N Drivers (4 Motors, PWM freq: {config.PWM_FREQUENCY} Hz)...")
        try:
            # Driver #1: Left Side Motors
            self.lf_fwd = PWMOutputDevice(config.PIN_LEFT_FRONT_FWD, frequency=config.PWM_FREQUENCY, initial_value=0.0)
            self.lf_rev = PWMOutputDevice(config.PIN_LEFT_FRONT_REV, frequency=config.PWM_FREQUENCY, initial_value=0.0)
            self.lr_fwd = PWMOutputDevice(config.PIN_LEFT_REAR_FWD, frequency=config.PWM_FREQUENCY, initial_value=0.0)
            self.lr_rev = PWMOutputDevice(config.PIN_LEFT_REAR_REV, frequency=config.PWM_FREQUENCY, initial_value=0.0)

            # Driver #2: Right Side Motors
            self.rf_fwd = PWMOutputDevice(config.PIN_RIGHT_FRONT_FWD, frequency=config.PWM_FREQUENCY, initial_value=0.0)
            self.rf_rev = PWMOutputDevice(config.PIN_RIGHT_FRONT_REV, frequency=config.PWM_FREQUENCY, initial_value=0.0)
            self.rr_fwd = PWMOutputDevice(config.PIN_RIGHT_REAR_FWD, frequency=config.PWM_FREQUENCY, initial_value=0.0)
            self.rr_rev = PWMOutputDevice(config.PIN_RIGHT_REAR_REV, frequency=config.PWM_FREQUENCY, initial_value=0.0)

            self.all_devices = [
                self.lf_fwd, self.lf_rev, self.lr_fwd, self.lr_rev,
                self.rf_fwd, self.rf_rev, self.rr_fwd, self.rr_rev
            ]
            print(f"[Motors] Hardware initialized:")
            print(f"  Driver 1 (Left):  Front(GPIO {config.PIN_LEFT_FRONT_FWD},{config.PIN_LEFT_FRONT_REV}), Rear(GPIO {config.PIN_LEFT_REAR_FWD},{config.PIN_LEFT_REAR_REV})")
            print(f"  Driver 2 (Right): Front(GPIO {config.PIN_RIGHT_FRONT_FWD},{config.PIN_RIGHT_FRONT_REV}), Rear(GPIO {config.PIN_RIGHT_REAR_FWD},{config.PIN_RIGHT_REAR_REV})")
            print("[Motors] Hardware GPIO successfully initialized. Motors are disabled.")
        except Exception as e:
            print(f"[Motors] Warning: Hardware GPIO init failed ({e}). Switching to Mock.")
            self.mock = True

    def _watchdog_loop(self):
        """Monitors command age; triggers safety stop if controller goes silent."""
        while self.is_running:
            if self.current_action != config.ACTION_STOP:
                age = time.perf_counter() - self.last_command_time
                if age > config.WATCHDOG_TIMEOUT_S:
                    # Stale command: emergency stop motors
                    self.stop(reason="WATCHDOG_TIMEOUT")
            time.sleep(0.05)

    def _set_channel(self, is_left: bool, speed: float):
        """
        Drives a single motor track (Left or Right, driving both front & rear motors).
        speed in [-1.0, 1.0], where positive is forward, negative is reverse.
        """
        # Apply direction inversion if physical motors are wired inverted
        effective_speed = -speed if (is_left and self.invert_left) or ((not is_left) and self.invert_right) else speed

        # Clamp speed to software safety ceiling
        capped_speed = max(-config.MAX_SPEED_DUTY, min(config.MAX_SPEED_DUTY, float(effective_speed)))
        abs_duty = abs(capped_speed)

        if self.mock:
            return

        if is_left:
            # Drive both Left Front and Left Rear motors together
            if capped_speed > 0.001:
                self.lf_fwd.value = abs_duty
                self.lf_rev.value = 0.0
                self.lr_fwd.value = abs_duty
                self.lr_rev.value = 0.0
            elif capped_speed < -0.001:
                self.lf_fwd.value = 0.0
                self.lf_rev.value = abs_duty
                self.lr_fwd.value = 0.0
                self.lr_rev.value = abs_duty
            else:
                self.lf_fwd.value = 0.0
                self.lf_rev.value = 0.0
                self.lr_fwd.value = 0.0
                self.lr_rev.value = 0.0
        else:
            # Drive both Right Front and Right Rear motors together
            if capped_speed > 0.001:
                self.rf_fwd.value = abs_duty
                self.rf_rev.value = 0.0
                self.rr_fwd.value = abs_duty
                self.rr_rev.value = 0.0
            elif capped_speed < -0.001:
                self.rf_fwd.value = 0.0
                self.rf_rev.value = abs_duty
                self.rr_fwd.value = 0.0
                self.rr_rev.value = abs_duty
            else:
                self.rf_fwd.value = 0.0
                self.rf_rev.value = 0.0
                self.rr_fwd.value = 0.0
                self.rr_rev.value = 0.0

    def forward(self, speed: float = config.SPEED_FORWARD):
        """Drives both left and right tracks forward."""
        self.last_command_time = time.perf_counter()
        self.current_action = config.ACTION_FORWARD
        self._set_channel(is_left=True, speed=speed)
        self._set_channel(is_left=False, speed=speed)

    def reverse(self, speed: float = config.SPEED_FORWARD):
        """Drives both left and right tracks in reverse."""
        self.last_command_time = time.perf_counter()
        self.current_action = "REVERSE"
        self._set_channel(is_left=True, speed=-speed)
        self._set_channel(is_left=False, speed=-speed)

    def pivot_left(self, speed: float = config.SPEED_TURN):
        """Pivots robot left in place (left reverse, right forward)."""
        self.last_command_time = time.perf_counter()
        self.current_action = config.ACTION_TURN_LEFT
        self._set_channel(is_left=True, speed=-speed)
        self._set_channel(is_left=False, speed=speed)

    def pivot_right(self, speed: float = config.SPEED_TURN):
        """Pivots robot right in place (left forward, right reverse)."""
        self.last_command_time = time.perf_counter()
        self.current_action = config.ACTION_TURN_RIGHT
        self._set_channel(is_left=True, speed=speed)
        self._set_channel(is_left=False, speed=-speed)

    def stop(self, reason: str = "NORMAL"):
        """Instantly stops all motors by zeroing PWM and direction pins."""
        self.last_command_time = time.perf_counter()
        self.current_action = config.ACTION_STOP
        self._set_channel(is_left=True, speed=0.0)
        self._set_channel(is_left=False, speed=0.0)

    def cleanup(self):
        """Safely de-energizes all motors and closes GPIO channels."""
        self.is_running = False
        self.stop(reason="SHUTDOWN")
        if not self.mock and hasattr(self, "all_devices"):
            for dev in self.all_devices:
                try:
                    dev.close()
                except Exception:
                    pass
        print("[Motors] Hardware safely de-energized and cleaned up.")


if __name__ == "__main__":
    print("[Motors] Testing motor controller...")
    mc = L298NMotorController()
    try:
        print("Testing Forward...")
        mc.forward(0.3)
        time.sleep(0.5)
        print("Testing Pivot Left...")
        mc.pivot_left(0.3)
        time.sleep(0.5)
        print("Testing Pivot Right...")
        mc.pivot_right(0.3)
        time.sleep(0.5)
        print("Testing Stop...")
        mc.stop()
    finally:
        mc.cleanup()
