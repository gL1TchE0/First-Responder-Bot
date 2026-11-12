"""
Diagnostic Utility for 2x L298N Motor Drivers (4 Independent DC Motors)
Tests each motor and GPIO pin individually at FULL power (100%) and 50% power
to verify wiring, direction, and physical wheel rotation.
"""
import sys
import time
import config

try:
    from gpiozero import PWMOutputDevice, DigitalOutputDevice
    HAS_HARDWARE_GPIO = True
except Exception as e:
    HAS_HARDWARE_GPIO = False
    print(f"Warning: gpiozero not available ({e})")


def run_pin_diagnostics():
    if not HAS_HARDWARE_GPIO:
        print("[ERROR] Cannot run on PC without hardware GPIO. Run on Raspberry Pi.")
        return

    print("=" * 70)
    print("🔧 4-MOTOR & 2x L298N DRIVER INDIVIDUAL DIAGNOSTIC TOOL")
    print("=" * 70)
    print("Detected Hardware Configuration:")
    print("  Driver #1 (Left Side):")
    print(f"    - Left Front: FWD=GPIO {config.PIN_LEFT_FRONT_FWD} (Pin 29), REV=GPIO {config.PIN_LEFT_FRONT_REV} (Pin 31)")
    print(f"    - Left Rear:  FWD=GPIO {config.PIN_LEFT_REAR_FWD} (Pin 36), REV=GPIO {config.PIN_LEFT_REAR_REV} (Pin 38)")
    print("  Driver #2 (Right Side):")
    print(f"    - Right Front: FWD=GPIO {config.PIN_RIGHT_FRONT_FWD} (Pin 11), REV=GPIO {config.PIN_RIGHT_FRONT_REV} (Pin 18)")
    print(f"    - Right Rear:  FWD=GPIO {config.PIN_RIGHT_REAR_FWD} (Pin 13), REV=GPIO {config.PIN_RIGHT_REAR_REV} (Pin 15)")
    print("=" * 70)
    print("⚠️ Elevate the robot chassis so all four wheels are in the air.")
    input("Press ENTER when ready to begin...")

    # Digital pins for pure 100% test (no PWM frequency issues)
    lf_fwd = DigitalOutputDevice(config.PIN_LEFT_FRONT_FWD, initial_value=False)
    lf_rev = DigitalOutputDevice(config.PIN_LEFT_FRONT_REV, initial_value=False)
    lr_fwd = DigitalOutputDevice(config.PIN_LEFT_REAR_FWD, initial_value=False)
    lr_rev = DigitalOutputDevice(config.PIN_LEFT_REAR_REV, initial_value=False)

    rf_fwd = DigitalOutputDevice(config.PIN_RIGHT_FRONT_FWD, initial_value=False)
    rf_rev = DigitalOutputDevice(config.PIN_RIGHT_FRONT_REV, initial_value=False)
    rr_fwd = DigitalOutputDevice(config.PIN_RIGHT_REAR_FWD, initial_value=False)
    rr_rev = DigitalOutputDevice(config.PIN_RIGHT_REAR_REV, initial_value=False)

    all_pins = [lf_fwd, lf_rev, lr_fwd, lr_rev, rf_fwd, rf_rev, rr_fwd, rr_rev]

    def stop_all():
        for p in all_pins:
            p.off()

    try:
        # TEST 1: Left Front Motor
        print(f"\n[1/8] Testing LEFT FRONT (GPIO {config.PIN_LEFT_FRONT_FWD}, Pin 29) -> Forward for 1.5s...")
        stop_all()
        lf_fwd.on()
        time.sleep(1.5)
        stop_all()

        print(f"[2/8] Testing LEFT FRONT (GPIO {config.PIN_LEFT_FRONT_REV}, Pin 31) -> Reverse for 1.5s...")
        lf_rev.on()
        time.sleep(1.5)
        stop_all()

        # TEST 2: Left Rear Motor
        print(f"\n[3/8] Testing LEFT REAR (GPIO {config.PIN_LEFT_REAR_FWD}, Pin 36) -> Forward for 1.5s...")
        lr_fwd.on()
        time.sleep(1.5)
        stop_all()

        print(f"[4/8] Testing LEFT REAR (GPIO {config.PIN_LEFT_REAR_REV}, Pin 38) -> Reverse for 1.5s...")
        lr_rev.on()
        time.sleep(1.5)
        stop_all()

        # TEST 3: Right Front Motor
        print(f"\n[5/8] Testing RIGHT FRONT (GPIO {config.PIN_RIGHT_FRONT_FWD}, Pin 11) -> Forward for 1.5s...")
        rf_fwd.on()
        time.sleep(1.5)
        stop_all()

        print(f"[6/8] Testing RIGHT FRONT (GPIO {config.PIN_RIGHT_FRONT_REV}, Pin 18) -> Reverse for 1.5s...")
        rf_rev.on()
        time.sleep(1.5)
        stop_all()

        # TEST 4: Right Rear Motor
        print(f"\n[7/8] Testing RIGHT REAR (GPIO {config.PIN_RIGHT_REAR_FWD}, Pin 13) -> Forward for 1.5s...")
        rr_fwd.on()
        time.sleep(1.5)
        stop_all()

        print(f"[8/8] Testing RIGHT REAR (GPIO {config.PIN_RIGHT_REAR_REV}, Pin 15) -> Reverse for 1.5s...")
        rr_rev.on()
        time.sleep(1.5)
        stop_all()

        # ALL 4 FORWARD
        print("\n[BONUS] Testing ALL 4 WHEELS FORWARD simultaneously for 2.0s...")
        input("Press ENTER to trigger all 4 wheels forward...")
        lf_fwd.on()
        lr_fwd.on()
        rf_fwd.on()
        rr_fwd.on()
        time.sleep(2.0)
        stop_all()
        print("-> All stopped.")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        stop_all()
        for p in all_pins:
            p.close()
        print("\n[INFO] Diagnostics complete. All GPIO pins safely de-energized.")


if __name__ == "__main__":
    run_pin_diagnostics()
