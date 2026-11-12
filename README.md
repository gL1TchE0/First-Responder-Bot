# First Responder Bot: Offline AI Vision-Based Autonomous Navigation Rover

[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/products/raspberry-pi-5/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![OS](https://img.shields.io/badge/OS-Raspberry%20Pi%20OS%20Bookworm%20(64--bit)-purple.svg)](https://www.raspberrypi.com/software/)
[![Model](https://img.shields.io/badge/Inference-YOLOv8n%20(Ultralytics)-brightgreen.svg)](https://github.com/ultralytics/ultralytics)
[![Control](https://img.shields.io/badge/Locomotion-4WD%20Skid--Steer%20(Dual%20L298N)-orange.svg)]()
[![Status](https://img.shields.io/badge/Air--Gapped-100%25%20Offline-success.svg)]()

An autonomous, edge-processed mobile robotic platform engineered for air-gapped indoor reconnaissance in hazardous environments and forensic crime scene investigations. The robot captures live visual scenes via a standard UVC USB webcam, executes an onboard **YOLOv8n** deep neural network entirely on the **Raspberry Pi 5 CPU**, evaluates spatial visual risks across Left, Center, and Right zones, and commands a **4WD skid-steer chassis via dual L298N dual H-bridge motor drivers**.


---

## Academic Information

- **Course:** 23CSE472 – Artificial Intelligence and Robotics
- **Department:** Department of Computer Science and Engineering
- **Institution:** School of Computing, Amrita Vishwa Vidyapeetham, Coimbatore, India
- **Project Mentor:** Dr. A. Baskar
- **Student Names and Registration Numbers:**
  - AJAY N MUKUNTH — CB.SC.U4CSE23006
  - ASHWIN V — CB.SC.U4CSE23009
  - SAKTHI KARTHIK B C — CB.SC.U4CSE23010
  - BALAJI N — CB.SC.U4CSE23011
  - KANHA B S — CB.SC.U4CSE23035

---

## Table of Contents
1. [Key Features](#key-features)
2. [Repository Structure](#repository-structure)
3. [System Hardware Architecture](#system-hardware-architecture)
4. [Pin Assignment & Wiring Map](#pin-assignment--wiring-map)
5. [Critical Electrical Safety Rules](#critical-electrical-safety-rules)
6. [Step-by-Step Installation & Setup](#step-by-step-installation--setup)
7. [Offline Air-Gapped Model Verification](#offline-air-gapped-model-verification)
8. [Pre-Flight Motor Testing & Calibration](#pre-flight-motor-testing--calibration)
9. [Running the Autonomous Robot](#running-the-autonomous-robot)
10. [Automated Unit Testing](#automated-unit-testing)
11. [Defensive Safety Systems](#defensive-safety-systems)
12. [Honest Engineering Limitations](#honest-engineering-limitations)
13. [Troubleshooting Guide](#troubleshooting-guide)

---

## Key Features

- **On-Device Edge Neural Inference:** Executes YOLOv8n object detection locally on the Raspberry Pi 5 Cortex-A76 CPU, sustaining 15–18.5 FPS at 320x320 resolution without requiring an external accelerator or GPU.
- **Threaded Buffer-Draining Video Pipeline:** Background capture worker drains V4L2/OpenCV hardware buffers in real time, guaranteeing image retrieval with under 20 ms sensor age.
- **3-Zone Spatial Risk Decomposition:** Partitions the horizontal visual plane into Left (0.00–0.35), Center (0.35–0.65), and Right (0.65–1.00) zones.
- **Ground Region of Interest (ROI) Filter:** Vertical thresholding (`y2 / H >= 0.35`) ensures overhead lights, ceiling fixtures, and distant background elements are ignored.
- **Strict Human Safety Protocol:** Detects humans with highest priority (weight 1.5); immediately halts if a person is in the forward path or occupies >= 25% of the frame, and veers away if detected in the lateral periphery.
- **Dual Software Watchdogs:** Independent daemon threads enforce an emergency stop if the camera frame age exceeds 800 ms or if motor commands stall for longer than 500 ms.
- **Software Direction Calibration:** Inverted DC motor polarity can be corrected instantly via `MOTOR_INVERT_LEFT` and `MOTOR_INVERT_RIGHT` flags in `config.py` with zero rewiring.

### Demonstration Video
A video demonstration of the physical robot navigating and avoiding obstacles autonomously is included: [`Demo_Video.mp4`](Demo_Video.mp4).

---

## Repository Structure

```text
ai_navigation/
├── Demo_Video.mp4          # Recorded physical demonstration video
├── ai_detector.py          # YOLOv8 perception engine & visual HUD renderer
├── camera.py               # Multi-threaded buffer-draining USB camera interface
├── config.py               # Global parameters, GPIO pins, speeds, and zone thresholds
├── diagnose_motors.py      # Low-level diagnostic utility for individual GPIO & pin testing
├── download_model.py       # Offline model weight downloader and SHA-256 verification
├── find_right_pins.py      # Automated pin scanning utility for physical GPIO mapping
├── main.py                 # Primary application orchestrator (Headless & GUI HUD modes)
├── motor_controller.py     # 4WD dual L298N H-Bridge driver with safety watchdog
├── navigation.py           # Reactive spatial reasoning & Human Safety Protocol engine
├── requirements.txt        # Python package dependencies
├── test_motors.py          # Interactive 5-step elevated wheel calibration tool
├── models/                 # Directory holding local model weights (yolov8n.pt)
│   └── .gitkeep
├── logs/                   # Directory for runtime execution logs
│   └── .gitkeep
└── tests/                  # Automated hardware-independent unit tests
    ├── test_ai_detector.py # Unit tests for detection structures and mock interfaces
    ├── test_motor_logic.py # Unit tests for action states, speed clamping, and inversion
    └── test_navigation.py  # Unit tests for spatial risks, human safety, and fail-safes
```

---

## System Hardware Architecture

### Bill of Materials (BOM)
- **Single Board Computer (SBC):** Raspberry Pi 5 (8 GB or 4 GB RAM, Quad-Core Cortex-A76 @ 2.4 GHz)
- **Camera:** Standard UVC USB 2.0/3.0 Webcam (connected to Pi 5 blue USB 3.0 port)
- **Chassis:** 4WD Robot Chassis with 4x Geared DC Motors
- **Motor Drivers:** 2x L298N Dual Full H-Bridge Modules (Driver #1: Left Front & Left Rear; Driver #2: Right Front & Right Rear)
- **Motor Power Supply:** 11.1V – 12.6V 3S LiPo Battery Pack (dedicated to L298N 12V terminals)
- **Logic Power Supply:** 5V / 3A USB-C Power Bank (dedicated to Raspberry Pi 5 USB-C port)
- **Emergency Hardware Cutoff:** SPST Toggle or Rocker Switch on 12V Battery (+) wire

---

## Pin Assignment & Wiring Map

Both L298N drivers operate in **4-Wire Direct PWM Mode** with onboard `ENA` and `ENB` headers shorted to 5V via jumpers.

### Driver #1 (Left Side Motors):
| Module Pin | Controlled Motors | Pi 5 Physical Pin | BCM GPIO | Functional Role |
| :---: | :---: | :---: | :---: | :--- |
| **`ENA`** | Left Front Speed | — | — | **SHORTED with onboard jumper to 5V** |
| **`IN1`** | Left Front Forward | **Physical Pin 29** | **GPIO 5** | Left Front Forward (PWM) |
| **`IN2`** | Left Front Reverse | **Physical Pin 31** | **GPIO 6** | Left Front Reverse (PWM) |
| **`IN3`** | Left Rear Forward | **Physical Pin 36** | **GPIO 16** | Left Rear Forward (PWM) |
| **`IN4`** | Left Rear Reverse | **Physical Pin 38** | **GPIO 20** | Left Rear Reverse (PWM) |
| **`ENB`** | Left Rear Speed | — | — | **SHORTED with onboard jumper to 5V** |
| **`GND`** | Ground Reference | **Physical Pin 6** | **GND** | **COMMON GROUND (Battery (-) & Pi GND)** |
| **`12V`** | Motor Power Positive | — | — | Connect to 12V LiPo Battery (+) via E-Stop |

### Driver #2 (Right Side Motors):
| Module Pin | Controlled Motors | Pi 5 Physical Pin | BCM GPIO | Functional Role |
| :---: | :---: | :---: | :---: | :--- |
| **`ENA`** | Right Front Speed | — | — | **SHORTED with onboard jumper to 5V** |
| **`IN1`** | Right Front Forward | **Physical Pin 11** | **GPIO 17** | Right Front Forward (PWM) |
| **`IN2`** | Right Front Reverse | **Physical Pin 18** | **GPIO 24** | Right Front Reverse (PWM) |
| **`IN3`** | Right Rear Forward | **Physical Pin 13** | **GPIO 27** | Right Rear Forward (PWM) |
| **`IN4`** | Right Rear Reverse | **Physical Pin 15** | **GPIO 22** | Right Rear Reverse (PWM) |
| **`ENB`** | Right Rear Speed | — | — | **SHORTED with onboard jumper to 5V** |
| **`GND`** | Ground Reference | **Physical Pin 14** | **GND** | **COMMON GROUND (Battery (-) & Pi GND)** |
| **`12V`** | Motor Power Positive | — | — | Connect to 12V LiPo Battery (+) via E-Stop |

---

## Critical Electrical Safety Rules

1. **Independent Power Supplies:**
   - Power the **Raspberry Pi 5 exclusively through its USB-C port** using a dedicated 5V/3A power bank or official adapter.
   - Power the **motors and L298N drivers strictly from the 12V LiPo battery**.
   - **Never connect an uncalibrated buck converter** from the 12V battery directly into the Pi's 5V GPIO header. Inductive voltage spikes and back-EMF from stalling DC motors can permanently destroy the Raspberry Pi PMIC.
2. **Mandatory Common Ground Reference:**
   - Connect the **negative terminal of the 12V battery**, the **GND terminals of both L298N drivers**, and **Pin 6/14 (GND)** of the Raspberry Pi 5 together. Without this shared ground, logic voltage levels float, inducing unpredictable motor triggering.
3. **L298N 5V Regulator Jumper:**
   - Keep the small `5V-EN` jumper on both L298N boards. This allows the onboard 78M05 linear regulator to power the L298N internal logic from the 12V supply.
   - Leave the L298N `5V` screw terminal unconnected.
4. **Physical Emergency Cutoff:**
   - Install a heavy-duty SPST switch on the positive wire of the 12V battery within easy reach.

---

## Step-by-Step Installation & Setup

Execute these commands in the terminal of your Raspberry Pi 5 running **Raspberry Pi OS Bookworm (64-bit)**:

### Step 1: Install System Packages & Hardware GPIO Libraries
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-gpiozero python3-lgpio v4l-utils libgl1 libglib2.0-0
```

### Step 2: Clone the Repository & Configure Virtual Environment
```bash
# Clone the repository
git clone https://github.com/your-username/ai_navigation.git
cd ai_navigation

# Create venv with system site-packages (required to access lgpio and gpiozero)
python3 -m venv --system-site-packages venv

# Activate the virtual environment
source venv/bin/activate
```

### Step 3: Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Offline Air-Gapped Model Verification

Before deploying into an air-gapped environment without internet access, run:

```bash
python download_model.py
```

### What This Script Does:
1. Downloads the official `yolov8n.pt` model weights (~6.5 MB) if not already present in `models/`.
2. Computes and displays the SHA-256 hash to confirm file integrity.
3. Performs a warm-up inference on a dummy tensor on the Pi 5 CPU.
4. Verifies that the system can run completely offline with zero external network calls.

### Manual Setup (For Completely Air-Gapped Machines):
1. Download `yolov8n.pt` from the official Ultralytics release:
   `https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n.pt`
2. Copy the `.pt` file onto a USB flash drive.
3. Transfer the file into the project folder at `ai_navigation/models/yolov8n.pt`.
4. Run `python download_model.py` to confirm verification passes.

---

## Pre-Flight Motor Testing & Calibration

> **SAFETY WARNING:** Elevate the robot chassis so all four wheels spin freely in the air before conducting floor runs.

Run the interactive calibration script:
```bash
python test_motors.py
```

The script guides you through:
1. **Forward Test:** Verifies all 4 wheels spin forward.
2. **Reverse Test:** Verifies all 4 wheels spin reverse.
3. **Pivot Left Test:** Left wheels spin reverse, right wheels spin forward.
4. **Pivot Right Test:** Left wheels spin forward, right wheels spin reverse.
5. **Emergency Stop Test:** Confirms motors brake immediately to 0.0 duty.

### Direction Calibration:
If a motor pair spins backward during the forward test:
- Left side reversed: Open `config.py` and set `MOTOR_INVERT_LEFT = True`.
- Right side reversed: Open `config.py` and set `MOTOR_INVERT_RIGHT = True`.
*(Zero physical rewiring required!)*

---

## Running the Autonomous Robot

### Mode A: Headless Console Mode (Recommended for SSH Battery Runs)
```bash
python main.py --headless
```
Live telemetry is displayed in the terminal:
```text
Step 0042 | Action: FORWARD    | Infer: 28.4ms | FPS: 15.2 | CPU: 41.2% | Risks [L:0.00 C:0.02 R:0.00] | Obs: chair(74%)
Step 0043 | Action: TURN_LEFT  | Infer: 29.1ms | FPS: 15.0 | CPU: 42.0% | Risks [L:0.00 C:0.24 R:0.18] | Obs: box(81%)
  -> REASON: OBSTACLE AVOIDANCE: Center blocked (0.24), Left opening clearer (0.00 < 0.18)
```

### Mode B: Visual HUD Window Mode (HDMI Monitor / VNC)
```bash
python main.py
```
Opens an OpenCV visual display rendering real-time bounding boxes, lateral zone dividers, the ground ROI line, and active motion banners.
- Press **`q`** or **`ESC`** to safely stop motors and exit.
- Press **`SPACEBAR`** for an immediate manual emergency stop.

---

## Automated Unit Testing

The project includes an automated unit test suite that validates perception geometry, spatial risk evaluation, human safety overrides, and motor controllers without requiring physical hardware:

```bash
python -m unittest discover tests
```

Expected output:
```text
Ran 19 tests in 0.005s
OK
```

All 19 tests run deterministically in synthetic mock mode to guarantee software stability before hardware deployment.

---

## Defensive Safety Systems

1. **Human Safety Protocol:** People are treated with the highest hazard weighting (1.5). The robot immediately halts if a person is in the central corridor or occupies >= 25% of the frame area, and steers away if a person appears in the lateral periphery.
2. **Camera Stale Frame Fail-Safe:** If the video stream freezes or a cable disconnects and frame age exceeds 0.8 seconds, the navigation engine commands an immediate emergency halt.
3. **Motor Command Watchdog:** An independent daemon thread halts all motors if no fresh command is received within 500 ms.
4. **Software Speed Capping:** Maximum motor duty cycle is capped at 50% (`MAX_SPEED_DUTY = 0.50`), preventing uncontrolled acceleration indoors.
5. **Clean Signal Handling:** `SIGINT` (Ctrl+C) and `SIGTERM` triggers de-energize all GPIO pins and cleanly close camera handles.

---

## Honest Engineering Limitations

- **Scale Ambiguity of 2D Vision:** The monocular camera provides 2D pixel bounds rather than true metric distance. The robot uses bounding box vertical placement (`y2`) and area fraction as proximity heuristics.
- **No Wheel Odometry / IMU:** The robot operates purely on reactive visual feedback without dead-reckoning trajectory estimation.
- **Negative Obstacle Invisibility:** Standard 2D object detectors classify positive obstacles (chairs, boxes, people). Drop-offs, stairwells, and floor holes are not classified; **operate strictly on flat indoor floors**.
- **Transparent / Specular Obstacles:** Clear glass partitions and mirrors are not recognized by 2D object detectors and require future ultrasonic/time-of-flight sensor fusion.

---

## Troubleshooting Guide

| Issue | Likely Cause | Exact Solution |
| :--- | :--- | :--- |
| **`ImportError: No module named lgpio`** | Virtual environment cannot access system `lgpio` | Recreate virtual environment with `--system-site-packages`: `python3 -m venv --system-site-packages venv` |
| **Camera fails to open (`index 0`)** | USB webcam assigned to different device index | Run `v4l2-ctl --list-devices`. Update `CAMERA_DEVICE_INDEX` in `config.py` (e.g., set to `1`). |
| **Motors do not spin** | Missing common ground or power switch OFF | 1. Connect L298N GND to Raspberry Pi GND (Pin 6).<br>2. Confirm 12V battery switch is ON.<br>3. Verify `ENA`/`ENB` jumpers are connected. |
| **Robot turns when commanded FORWARD** | One motor pair wired in reverse polarity | Run `python test_motors.py`. Set `MOTOR_INVERT_LEFT = True` or `MOTOR_INVERT_RIGHT = True` in `config.py`. |
| **Low FPS / Stuttering** | Model input resolution too high | Ensure `INFERENCE_IMAGE_SIZE = 320` in `config.py`. |
| **Robot halts with `FAIL-SAFE: Camera stale`** | USB port underpowered or loose cable | Connect webcam directly to a blue USB 3.0 port on the Raspberry Pi 5. |

---

## License & Academic Attribution

This project is developed for academic and research purposes under the course **23CSE472 – Artificial Intelligence and Robotics** at **Amrita Vishwa Vidyapeetham, Coimbatore, India**.
Code released under the [MIT License](https://opensource.org/licenses/MIT).
