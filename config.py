# config.py

import os

# --- API KEYS ---
# You can set these in your environment variables or paste them directly here.
# WARNING: Do not share this file publicly if you paste real keys here.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")

# --- HARDWARE CONFIGURATION ---
# Camera Index: 0 is usually the built-in webcam, 1 is often an external USB camera.
# Try changing this if the robot cannot see.
CAMERA_INDEX = 1

# Serial Port for Arduino (e.g., '/dev/ttyACM0' on Linux, 'COM3' on Windows)
# Set to None to attempt auto-detection or if not using Arduino.
SERIAL_PORT = None
BAUD_RATE = 9600

# --- AUDIO CONFIGURATION (ULTRA-OPTIMIZED) ---
MIC_SAMPLE_RATE = 16000
MIC_CHANNELS = 1
MIC_CHUNK_SIZE = 256  # Reduced from 512 for ultra-low latency
STT_ENERGY_THRESHOLD = 250  # Further reduced for instant detection
STT_SILENCE_DURATION = 0.6  # Reduced from 0.8 for faster response

# --- FACE TRACKING CONFIGURATION (OPTIMIZED) ---
# Servo Angles (Degrees)
SERVO_MIN_ANGLE = 30
SERVO_MAX_ANGLE = 110
SERVO_NEUTRAL_ANGLE = 80

# Vertical Eye Movement (The "Absolute Cinema" Version)
EYE_V_MIN = 50   # Close (downward)
EYE_V_MID = 130
EYE_V_MAX = 180  # Far

# Face Detection Model Paths
# Ensure these files are in the same directory or provide absolute paths.
PROTOTXT_PATH = "deploy.prototxt"
CAFFEMODEL_PATH = "res10_300x300_ssd_iter_140000.caffemodel"
CONFIDENCE_THRESHOLD = 0.65  # Lowered for more responsive detection

# --- NATURAL CONVERSATION CONFIGURATION ---
CONVERSATION_PAUSE_SHORT = 0.15   # Comma pauses
CONVERSATION_PAUSE_LONG = 0.4     # Sentence pauses
GESTURE_THINKING_DELAY = 0.8      # Thinking gesture timing
GESTURE_AFFIRMATIVE_DELAY = 0.6   # Nodding timing
INTERRUPT_RECOVERY_TIME = 0.3       # Recovery after interruption

# --- SUBCONSCIOUS MICRO-MOVEMENT CONFIGURATION ---
# These create "alive" feeling without being noticeable
MICRO_SACCADE_INTERVAL = 0.8      # Seconds between micro-saccades
MICRO_SACCADE_SIZE = 2            # Degrees (tiny movements)
BREATHING_CYCLE = 4.0               # Seconds per breath
BREATHING_AMPLITUDE = 1.5           # Degrees (subtle chest/head movement)
BLINK_MIN_INTERVAL = 2.5            # Minimum seconds between blinks
BLINK_MAX_INTERVAL = 6.0            # Maximum seconds between blinks
BLINK_DURATION = 0.15               # How long a blink lasts
IDLE_DRIFT_SPEED = 0.3              # Degrees per second
SUBCONSCIOUS_TWITCH_CHANCE = 0.02   # 2% chance per second of micro-twitch
PUPIL_DILATION_CYCLE = 8.0          # Seconds for pupil size cycle
ATTENTION_DECAY_RATE = 0.05         # How fast attention wanders when idle
MICRO_EXPRESSION_CHANCE = 0.03      # 3% chance per second of emotional micro-expression
MICRO_EXPRESSION_COOLDOWN = 3.0     # Minimum seconds between micro-expressions

# --- SYSTEM CONFIGURATION ---
CHAT_LOG_FILE = "chat_log.json"
CONVERSATION_HISTORY_FILE = "conversation_history.json"
CAPTURES_DIR = "captures"
