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

# --- AUDIO CONFIGURATION ---
MIC_SAMPLE_RATE = 16000
MIC_CHANNELS = 1
MIC_CHUNK_SIZE = 1024

# --- FACE TRACKING CONFIGURATION ---
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
CONFIDENCE_THRESHOLD = 0.7

# --- SYSTEM CONFIGURATION ---
CHAT_LOG_FILE = "chat_log.json"
CONVERSATION_HISTORY_FILE = "conversation_history.json"
CAPTURES_DIR = "captures"
