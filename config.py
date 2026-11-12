"""
Configuration module for Offline AI Vision-Based Navigation Robot
Platform: Raspberry Pi 5 (8GB) | OS: Raspberry Pi OS Bookworm | Python 3.11+
"""
from pathlib import Path

# ==============================================================================
# PATHS AND DIRECTORIES
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"

for d in [MODELS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Default model weight filename
# Supported: 'yolov8n.pt', 'yolo11n.pt', 'yolo26n.pt' (or exported .onnx)
MODEL_NAME = "yolov8n.pt"
MODEL_PATH = str(MODELS_DIR / MODEL_NAME)

# ==============================================================================
# HARDWARE PIN CONFIGURATION (Raspberry Pi 5 40-Pin Header - BCM GPIO Numbers)
# Hardware Architecture: 2x L298N Dual H-Bridge Drivers (4 Independent DC Motors)
# Both drivers have ENA & ENB shorted with jumpers (4-Wire direct PWM per driver)
# ==============================================================================

# L298N Driver #1: Left Side Motors (Left Front & Left Rear)
PIN_LEFT_FRONT_FWD = 5   # IN1 on Driver 1 (Physical Pin 29)
PIN_LEFT_FRONT_REV = 6   # IN2 on Driver 1 (Physical Pin 31)
PIN_LEFT_REAR_FWD  = 16  # IN3 on Driver 1 (Physical Pin 36)
PIN_LEFT_REAR_REV  = 20  # IN4 on Driver 1 (Physical Pin 38)

# L298N Driver #2: Right Side Motors (Right Front & Right Rear)
PIN_RIGHT_FRONT_FWD = 17 # IN1 on Driver 2 (Physical Pin 11)
PIN_RIGHT_FRONT_REV = 24 # IN2 on Driver 2 (Physical Pin 18)
PIN_RIGHT_REAR_FWD  = 27 # IN3 on Driver 2 (Physical Pin 13)
PIN_RIGHT_REAR_REV  = 22 # IN4 on Driver 2 (Physical Pin 15)

# Backward compatibility aliases for legacy single-driver imports
PIN_L298N_IN1 = PIN_LEFT_FRONT_FWD
PIN_L298N_IN2 = PIN_LEFT_FRONT_REV
PIN_L298N_IN3 = PIN_RIGHT_FRONT_FWD
PIN_L298N_IN4 = PIN_RIGHT_FRONT_REV
PIN_L298N_ENA = 12
PIN_L298N_ENB = 13
MOTOR_CONTROL_MODE = "4_WIRE"

# Direction Inversion Flags:
# Set to True if physical motor wiring causes left or right side to spin backward
MOTOR_INVERT_LEFT = False
MOTOR_INVERT_RIGHT = False

# ==============================================================================
# MOTOR SPEED LIMITS & PWM SETTINGS (Conservative, Beginner-Friendly Defaults)
# ==============================================================================
PWM_FREQUENCY = 1000      # 1 kHz PWM frequency (optimal for L298N BJT thermal dissipation)
MAX_SPEED_DUTY = 0.50     # Hard speed cap (50% max duty cycle for safety in indoor trials)
SPEED_FORWARD = 0.38      # Moderate forward cruising speed (~38% duty)
SPEED_TURN = 0.35         # Slow, controlled pivot turn speed (~35% duty)
SPEED_CREEP = 0.25        # Slow creep speed for narrow passages

# Step duration for reactive pulsed driving (seconds per movement command)
BURST_DURATION_S = 0.25   # Motors pulse for 250ms, then evaluate fresh perception frame
WATCHDOG_TIMEOUT_S = 0.50 # If no command received within 500ms, motors auto-stop

# ==============================================================================
# CAMERA CONFIGURATION
# ==============================================================================
CAMERA_DEVICE_INDEX = 0   # 0 for default USB webcam (/dev/video0)
FRAME_WIDTH = 640         # Standard capture width
FRAME_HEIGHT = 480        # Standard capture height
CAMERA_FPS = 15           # Target capture frame rate
FRAME_TIMEOUT_S = 0.8     # Stale frame threshold (triggers safety stop if stream stalls)

# ==============================================================================
# AI PERCEPTION SETTINGS (Optimized for Raspberry Pi 5 CPU)
# ==============================================================================
# Downscaled input resolution fed to YOLO for fast CPU inference (e.g., 320x320)
# 320x320 provides 15-20+ FPS on Pi 5 Quad-Core Cortex-A76 CPU
INFERENCE_IMAGE_SIZE = 320

CONFIDENCE_THRESHOLD = 0.35         # General object detection confidence threshold
PERSON_CONFIDENCE_THRESHOLD = 0.28  # Stricter sensitivity for human detection

# COCO Classes considered significant physical hazards for an indoor mobile robot
# People are treated with the highest safety priority
HAZARD_CLASSES = {
    "person": 1.0,         # Maximum hazard weight (never approach!)
    "chair": 0.8,
    "couch": 0.9,
    "bed": 0.9,
    "dining table": 0.9,
    "tv": 0.7,
    "laptop": 0.6,
    "potted plant": 0.8,
    "backpack": 0.7,
    "suitcase": 0.8,
    "bottle": 0.5,
    "box": 0.7,
    "sports ball": 0.6,
    "dog": 0.9,
    "cat": 0.9,
    "stop sign": 1.0
}

# ==============================================================================
# REACTIVE NAVIGATION ZONE CONFIGURATION
# ==============================================================================
# Visual Horizontal Zones (fraction of frame width 0.0 to 1.0)
ZONE_LEFT_END = 0.35      # Left zone: 0.00 to 0.35 (35% of frame)
ZONE_CENTER_START = 0.35  # Center zone: 0.35 to 0.65 (30% of frame)
ZONE_CENTER_END = 0.65
ZONE_RIGHT_START = 0.65   # Right zone: 0.65 to 1.00 (35% of frame)

# Ground Region of Interest (ROI)
# Objects whose bottom bounding box edge is above this line are considered in the background / air
GROUND_ROI_Y_MIN = 0.35   # Ignore objects only occupying top 35% of frame (ceiling lights, etc.)

# Visual Obstruction Thresholds
# Fraction of zone area occupied by detected hazard bounding boxes
OBSTRUCTION_THRESHOLD_CENTER = 0.12  # 12% center occupancy triggers turn or stop
OBSTRUCTION_THRESHOLD_SIDE = 0.20    # 20% side occupancy biases direction away
CRITICAL_PERSON_AREA = 0.08          # 8% frame area of person triggers immediate stop

# Action definitions
ACTION_FORWARD = "FORWARD"
ACTION_TURN_LEFT = "TURN_LEFT"
ACTION_TURN_RIGHT = "TURN_RIGHT"
ACTION_STOP = "STOP"
