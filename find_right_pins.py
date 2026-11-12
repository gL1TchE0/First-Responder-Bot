"""
Automatic GPIO Pin Scanner for Right Motors
Iterates through all possible Raspberry Pi GPIO pins, turning each on for 1.5 seconds.
Watch your Right Front and Right Rear wheels. When a wheel spins forward, note the GPIO number!
"""
import time
from gpiozero import OutputDevice

# Candidate GPIOs on Raspberry Pi 5 40-pin header (excluding already working left pins: 5, 6, 16, 20)
CANDIDATE_PINS = [
    (17, "Physical Pin 11"),
    (27, "Physical Pin 13"),
    (22, "Physical Pin 15"),
    (23, "Physical Pin 16"),
    (24, "Physical Pin 18"),
    (25, "Physical Pin 22"),
    (18, "Physical Pin 12"),
    (14, "Physical Pin 8"),
    (15, "Physical Pin 10"),
    (4,  "Physical Pin 7"),
    (26, "Physical Pin 37"),
    (19, "Physical Pin 35"),
    (13, "Physical Pin 33"),
    (12, "Physical Pin 32"),
]

def scan():
    print("=" * 65)
    print("🔍 AUTOMATIC GPIO PIN SCANNER FOR RIGHT FORWARD MOTORS")
    print("=" * 65)
    print("Watch your two RIGHT wheels carefully.")
    print("When you see a wheel spin FORWARD, remember the GPIO number on screen!")
    print("=" * 65)
    input("Press ENTER to start the scan...")

    for gpio, pin_desc in CANDIDATE_PINS:
        print(f"\n---> Activating GPIO {gpio} ({pin_desc}) for 2.0 seconds...")
        try:
            dev = OutputDevice(gpio, initial_value=False)
            dev.on()
            time.sleep(2.0)
            dev.off()
            dev.close()
        except Exception as e:
            print(f"     [Skip GPIO {gpio}: {e}]")
            continue

        print(f"     Done with GPIO {gpio}. Did either right wheel spin forward?")
        time.sleep(0.5)

    print("\n" + "=" * 65)
    print("Scan complete!")

if __name__ == "__main__":
    scan()
