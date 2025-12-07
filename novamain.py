import argparse
import novastt
import novatts
import novaresponse
import novafacetrack
import time
import json
import re
import os
import cv2
import novaweb
import config

parser = argparse.ArgumentParser(description='Nova Animatronic')
parser.add_argument('--camera-index', type=int, default=config.CAMERA_INDEX, help=f'Camera index for FaceTracker (default {config.CAMERA_INDEX})')
parser.add_argument('--port', type=str, default=config.SERIAL_PORT, help='Optional Arduino serial port (e.g., /dev/ttyACM0)')
args = parser.parse_args()

SHARED_CAMERA_INDEX = args.camera_index

def fix_ai():
    if not os.path.exists(config.CHAT_LOG_FILE):
        return
        
    with open(config.CHAT_LOG_FILE, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return

    # recursively replace "Nova" with "me"
    def replace_nova(obj):
        if isinstance(obj, dict):
            return {k: replace_nova(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_nova(v) for v in obj]
        elif isinstance(obj, str):
            return obj.replace("Nova", "me")
        else:
            return obj

    data = replace_nova(data)

    with open(config.CHAT_LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)


# --- HELPER FUNCTION FOR TAKING PICTURES ---
def take_picture_from_tracker(tracker_instance, save_dir=config.CAPTURES_DIR):
    """
    Safely gets the latest frame from the running face tracker thread
    and saves it to a file.

    Args:
        tracker_instance: The running FaceTracker object.
        save_dir (str): The directory where the image will be saved.

    Returns:
        str: The full path to the saved image, or None if it fails.
    """
    print("📸 Attempting to capture image...")
    frame = tracker_instance.get_latest_frame()

    if frame is None:
        print(
            "❌ ERROR: Could not get a frame from the camera tracker. Is the camera working?"
        )
        return None

    # Ensure the save directory exists
    os.makedirs(save_dir, exist_ok=True)

    # Create a unique filename based on the current time
    filename = f"capture_{int(time.time()*1000)}.jpg"
    path = os.path.join(save_dir, filename)

    # Save the frame to the specified path
    # Resize to speed up upload/processing (Max width 640)
    height, width = frame.shape[:2]
    if width > 640:
        scale = 640 / width
        new_height = int(height * scale)
        frame = cv2.resize(frame, (640, new_height))
        
    cv2.imwrite(path, frame)
    print(f"✅ Picture saved successfully to {path}")
    return path


# --- 1. INITIALISE ALL SERVICES ---

# Global variable to store the pre-emptively captured image
latest_captured_image_path = None

def capture_image_callback():
    """Callback to capture image when recording starts."""
    global latest_captured_image_path
    print("📸 Pre-emptive capture triggered...")
    latest_captured_image_path = take_picture_from_tracker(face_tracker)

# Speech-to-Text Service
stt_service = novastt.SpeechToText(on_record_start=capture_image_callback)

# Animatronic Speech/Movement (TTS) Service
robot = novatts.Animatronic()
robot.initialise(port_path=args.port)

# Face Tracker Background Service (This now controls the camera)
face_tracker = novafacetrack.FaceTracker(command_callback=robot.queue_command, camera_index=SHARED_CAMERA_INDEX)


# --- 2. START BACKGROUND PROCESSES ---

# Start the face tracker thread. It will run continuously in the background.
face_tracker.start()

# Start the Web Interface
web_interface = novaweb.WebInterface(stt_service, robot, face_tracker)
web_interface.start()

# Start the keyboard listener for STT ('c' to record, 's' to stop).
stt_service.start_listener()

# A brief pause to allow the camera to initialize fully before we might need it.
print("Waiting for camera to initialize...")
time.sleep(2)
print("✅ System ready.")


# --- 3. LOAD HISTORY AND PREPARE MAIN LOOP ---

print("\n" + "=" * 50)
print("Nova is running. Press 'c' to record, 's' to stop.")
print("🌐 Web Interface available at: http://localhost:5000")
print("Press Ctrl+C to exit the program gracefully.")
print("=" * 50 + "\n")

# Run the long-term memory summarizer once on startup.
novaresponse.long_term_memory_converter()

# Load the conversation history from the JSON file.
try:
    with open(config.CHAT_LOG_FILE, "r") as file:
        conversation_history = json.load(file)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Could not load conversation history ({e}), starting fresh.")
    # Define the correct structure if the file doesn't exist or is corrupt
    conversation_history = {"short_term": [], "long_term": [], "conversation": []}

# Compile regex patterns for efficient matching.
see_this_pattern = re.compile(r"(see this|look at|what do you see|describe this|what is that|what is in front|visual check|eyes|rate this|how does|what does|you see|can you see)", re.IGNORECASE)
visual_query_pattern = re.compile(r"#VISUAL", re.IGNORECASE)
search_query_pattern = re.compile(r"#SEARCH_QUERY", re.IGNORECASE)
fix_ai()

# --- 4. MAIN APPLICATION LOOP ---

try:
    print("✅ System ready. Press 'c' to talk.")

    while True:
        try:
            # Check if the STT service has transcribed new text.
            if stt_service.transcribed_text:
                text = stt_service.transcribed_text.strip()
                
                # Check for exit command
                if text == "#EXIT":
                    print("\n👋 Exit command received. Shutting down...")
                    break
                    
                print(f'\n🎤 User said: "{text}"')

                # A. Check for direct visual query patterns FIRST (Low Latency)
                if see_this_pattern.search(text):
                    print("👀 Direct visual query detected.")
                    
                    # Use pre-captured image if available, otherwise try to capture now
                    img_path = latest_captured_image_path
                    if not img_path:
                        print("⚠️ No pre-captured image found. Capturing now...")
                        img_path = take_picture_from_tracker(face_tracker)
                    else:
                        print(f"✅ Using pre-captured image: {img_path}")
                    
                    if img_path:  # Only proceed if the picture was taken successfully
                        output = novaresponse.query_with_image(
                            text, conversation_history, image_path=img_path
                        )
                        # FALLBACK: If visual AI says it's not visual, use regular LLM
                        if "not a visual query" in output.lower():
                            print("⚠️ Visual AI rejected query. Falling back to regular response.")
                            # We need a fresh response since the previous one was just the token
                            # But wait, if the previous one was just #VISUAL, we need to ask Groq again?
                            # Actually, if Groq said #VISUAL, it expects the visual AI to handle it.
                            # If Visual AI rejects it, we are in a bind. 
                            # Let's just have the robot say it can't see.
                            fallback_response = "I'm having trouble seeing that clearly right now."
                            robot.speak_text(fallback_response)
                            full_response_text = fallback_response
                        else:
                            robot.speak_text(output)
                            full_response_text = output
                    else:
                        # CAMERA FAILED - In-character fallback
                        fallback_response = "I can't see anything right now. My camera seems to be on strike. You'll have to describe it to me."
                        robot.speak_text(fallback_response)
                        full_response_text = fallback_response

                    novaresponse.save_response(text, full_response_text)
                    conversation_history["conversation"].append(
                        {"prompt": text, "response": full_response_text}
                    )
                    
                    # Clear the used image
                    latest_captured_image_path = None

                # B. Handle standard query (might trigger a visual or search query internally)
                else:
                    # Get full response from LLM (No longer a generator)
                    full_response_text = novaresponse.response(text, conversation_history)
                    
                    # Strip quotes and whitespace for token detection
                    cleaned_response = full_response_text.strip().strip('"').strip("'").strip()
                    
                    print(f"🔍 DEBUG: Raw LLM response: '{full_response_text}'")
                    print(f"🔍 DEBUG: Cleaned for matching: '{cleaned_response}'")
                    
                    if cleaned_response == "#VISUAL" or visual_query_pattern.search(cleaned_response):
                        print("🤖 Internal visual query triggered.")
                        
                        # Use pre-captured image if available
                        img_path = latest_captured_image_path
                        if not img_path:
                                print("⚠️ No pre-captured image found. Capturing now...")
                                img_path = take_picture_from_tracker(face_tracker)
                        else:
                            print(f"✅ Using pre-captured image: {img_path}")

                        if img_path:
                            output = novaresponse.query_with_image(
                                text, conversation_history, image_path=img_path
                            )
                            # FALLBACK: If visual AI says it's not visual, use regular LLM
                            if "not a visual query" in output.lower():
                                print("⚠️ Visual AI rejected query. Falling back to regular response.")
                                # We need a fresh response since the previous one was just the token
                                # But wait, if the previous one was just #VISUAL, we need to ask Groq again?
                                # Actually, if Groq said #VISUAL, it expects the visual AI to handle it.
                                # If Visual AI rejects it, we are in a bind. 
                                # Let's just have the robot say it can't see.
                                fallback_response = "I'm having trouble seeing that clearly right now."
                                robot.speak_text(fallback_response)
                                full_response_text = fallback_response
                            else:
                                robot.speak_text(output)
                                full_response_text = output
                        else:
                            # CAMERA FAILED - In-character fallback
                            fallback_response = "I can't see anything right now. My camera seems to be on strike. You'll have to describe it to me."
                            robot.speak_text(fallback_response)
                            full_response_text = fallback_response
                            
                        # Clear the used image
                        latest_captured_image_path = None
                    
                    elif search_query_pattern.search(cleaned_response):
                            # Handle search query
                            print("🔍 Search query triggered.")
                            search_result = novaresponse.search_response(text, conversation_history)
                            robot.speak_text(search_result)
                            full_response_text = search_result
                    
                    else:
                        # Standard response - Speak it directly
                        robot.speak_text(full_response_text)

                    novaresponse.save_response(text, full_response_text)
                    conversation_history["conversation"].append(
                        {"prompt": text, "response": full_response_text}
                    )
                    
                    # Clear the used image (if it wasn't used)
                    latest_captured_image_path = None
                # Reset the transcribed text to None so we don't process the same input again.
                stt_service.transcribed_text = None
                print("\nListening for next command...")
            
            # A small delay to prevent the loop from using 100% CPU.
            time.sleep(0.05)
            
        except Exception as e:
            print(f"\n❌ Error in main loop: {e}")
            stt_service.transcribed_text = None # Reset to avoid infinite error loop
            time.sleep(1)

        # A small delay to prevent the loop from using 100% CPU.
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n\n🛑 Program interrupted by user (Ctrl+C).")

finally:
    # --- 5. GRACEFUL SHUTDOWN ---
    print("Initiating shutdown sequence...")

    # Stop the face tracker's main loop.
    face_tracker.stop()

    # Shut down the animatronic's serial connection and motors.
    robot.shutdown()

    # Wait for the face tracker thread to finish its cleanup (releasing camera, etc.).
    if face_tracker.is_alive():
        # Join with a timeout to avoid hanging indefinitely.
        face_tracker.join(timeout=5)

    print("✅ All services have been stopped. Goodbye!")