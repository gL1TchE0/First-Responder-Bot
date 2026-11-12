"""
Standalone Interactive Motor Testing & Calibration Tool
Run this script on the Raspberry Pi 5 to verify L298N wiring, direction orientation,
and emergency stop behavior BEFORE placing the robot on the floor!
"""
import sys
import time
import config
from motor_controller import L298NMotorController


def run_motor_calibration():
    print("=" * 70)
    print("🚗 2x L298N 4WD SKID-STEER HARDWARE CALIBRATION & TEST")
    print("=" * 70)
    print("⚠️ SAFETY WARNING:")
    print("  1. Lift the robot chassis so all four wheels are elevated in the air.")
    print("  2. Keep hands and wires clear of the rotating wheels.")
    print("  3. Keep one hand ready on your 12V battery power switch as a physical E-stop.")
    print("=" * 70)

    try:
        input("\nPress ENTER when the wheels are elevated and ready to begin...")
    except EOFError:
        pass

    controller = L298NMotorController()

    try:
        # Step 1: Forward Test
        print("\n[Step 1/5] Testing FORWARD Motion (45% Speed for 1.5s)...")
        print("  -> All 4 wheels should spin forward.")
        controller.forward(speed=0.45)
        time.sleep(1.5)
        controller.stop()
        time.sleep(0.5)

        # Step 2: Reverse Test
        print("\n[Step 2/5] Testing REVERSE Motion (45% Speed for 1.5s)...")
        print("  -> All 4 wheels should spin backward.")
        controller.reverse(speed=0.45)
        time.sleep(1.5)
        controller.stop()
        time.sleep(0.5)

        # Step 3: Pivot Left Test
        print("\n[Step 3/5] Testing PIVOT LEFT Motion (45% Speed for 1.5s)...")
        print("  -> Left wheels spin REVERSE; Right wheels spin FORWARD.")
        controller.pivot_left(speed=0.45)
        time.sleep(1.5)
        controller.stop()
        time.sleep(0.5)

        # Step 4: Pivot Right Test
        print("\n[Step 4/5] Testing PIVOT RIGHT Motion (45% Speed for 1.5s)...")
        print("  -> Left wheels spin FORWARD; Right wheels spin REVERSE.")
        controller.pivot_right(speed=0.45)
        time.sleep(1.5)
        controller.stop()
        time.sleep(0.5)

        # Step 5: Emergency Stop Verification
        print("\n[Step 5/5] Testing Hard Emergency Stop...")
        controller.forward(speed=0.50)
        time.sleep(0.2)
        controller.stop(reason="EMERGENCY_STOP_TEST")
        print("  -> Motors instantly stopped.")

        print("\n" + "=" * 70)
        print("🔍 DIRECTION CALIBRATION CHECK:")
        print("Did either side spin in the wrong direction during the FORWARD test?")
        print("  - If the LEFT wheels spun backwards:  Set 'MOTOR_INVERT_LEFT = True' in config.py")
        print("  - If the RIGHT wheels spun backwards: Set 'MOTOR_INVERT_RIGHT = True' in config.py")
        print("=" * 70)
        print("✅ MOTOR HARDWARE CALIBRATION COMPLETE!")

    except KeyboardInterrupt:
        print("\n[Motors] Test interrupted by user. Stopping motors...")
    finally:
        controller.cleanup()


if __name__ == "__main__":
    run_motor_calibration()
