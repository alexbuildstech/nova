#!/usr/bin/env python3
import os
import sys
import time

print("🔍 Starting Nova System Verification...")

# 1. Environment Check
print(f"🐍 Python Version: {sys.version}")
print(f"📁 Workspace: {os.getcwd()}")

# 2. Dependency Check
requirements = [
    "groq", "google.genai", "cv2", "serial", "sounddevice", "pynput", "numpy", "flask", "requests"
]

missing = []
for lib in requirements:
    try:
        __import__(lib)
        print(f"✅ {lib} is installed.")
    except ImportError as e:
        print(f"❌ {lib} is MISSING: {e}")
        missing.append(lib)

if missing:
    print(f"\n🛑 Verification FAILED. Missing: {', '.join(missing)}")
    sys.exit(1)

# 3. Model Configuration Check
import config
print("\n⚙️ Model Configuration:")
print(f"   MAIN_MODEL: {config.MAIN_MODEL}")
print(f"   SEARCH_MODEL: {config.SEARCH_MODEL}")
print(f"   VISION_MODEL: {config.VISION_MODEL}")
print(f"   MEMORY_MODEL: {config.MEMORY_MODEL}")

# 4. Initialization Test (Dry Run)
print("\n🧪 Attempting basic module initialization (Dry Run)...")

try:
    import novaresponse
    import novatts
    import novastt
    import novafacetrack
    
    # Check if we can initialize the response system (uses ChromaDB)
    print("   Initializing response system (ChromaDB)...")
    mem = novaresponse.NovaMemory()
    print("   ✅ Memory system initialized.")
    
    # Mocking hardware for dry run
    print("   Checking Animatronic (novatts) initialization...")
    robot = novatts.Animatronic()
    # We won't call robot.initialise() because it starts background threads 
    # and might hang on pynput listener without X11.
    print("   ✅ Animatronic module loaded.")
    
    print("\n🎉 ALL SOFTWARE CHECKS PASSED!")
    
except Exception:
    import traceback
    print("\n❌ Initialization error:")
    traceback.print_exc()
    sys.exit(1)

sys.exit(0)
