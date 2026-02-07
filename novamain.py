#!/usr/bin/env python3
# novamain.py

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

# Parse command line arguments for hardware configuration
parser = argparse.ArgumentParser(description='Nova Animatronic - Advanced AI Robot Control System')
parser.add_argument('--camera-index', type=int, default=config.CAMERA_INDEX, help=f'Camera index for FaceTracker (default {config.CAMERA_INDEX})')
parser.add_argument('--port', type=str, default=config.SERIAL_PORT, help='Optional Arduino serial port (e.g., /dev/ttyACM0)')
args = parser.parse_args()

SHARED_CAMERA_INDEX = args.camera_index

def fix_ai():
    """
    Sanitizes the conversation history log to ensure consistent persona context.
    Replaces third-person references with first-person to maintain immersion.
    """
    if not os.path.exists(config.CHAT_LOG_FILE):
        return

    with open(config.CHAT_LOG_FILE, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return

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


def take_picture_from_tracker(tracker_instance, save_dir=config.CAPTURES_DIR):
    """
    Captures a high-resolution frame from the active computer vision thread.
    Used for visual analysis and object recognition tasks.
    """
    print("📸 Initiating image capture sequence...")
    frame = tracker_instance.get_latest_frame()

    if frame is None:
        print(
            "❌ ERROR: Video feed unavailable. Check camera connection."
        )
        return None

    os.makedirs(save_dir, exist_ok=True)

    filename = f"capture_{int(time.time()*1000)}.jpg"
    path = os.path.join(save_dir, filename)

    # Optimize image resolution for API transmission (Max width 640px)
    height, width = frame.shape[:2]
    if width > 640:
        scale = 640 / width
        new_height = int(height * scale)
        frame = cv2.resize(frame, (640, new_height))
        
    cv2.imwrite(path, frame)
    print(f"✅ Image successfully captured and archived: {path}")
    return path


# --- SERVICE INITIALIZATION ---

# Buffer for pre-emptive visual context capture
latest_captured_image_path = None

def smart_visual_capture(text):
    """
    Context-aware visual capture with conversational intelligence.
    """
    visual_keywords = ["see", "look", "what", "describe", "show", "rate", "check", "watch", "view", "camera"]
    contextual_indicators = ["this", "that", "here", "my", "your", "the", "a", "an"]
    
    text_lower = text.lower()
    
    # Check for visual keywords
    has_visual_keyword = any(keyword in text_lower for keyword in visual_keywords)
    
    # Context awareness - only trigger if asking about immediate context
    has_context = any(indicator in text_lower for indicator in contextual_indicators)
    
    # Smart detection: must have visual keyword + context OR direct question
    return has_visual_keyword and (has_context or '?' in text)


def conversation_flow_manager(current_input, conversation_history):
    """
    Natural conversation flow optimization for better dialogue continuity.
    """
    recent_exchanges = conversation_history.get("conversation", [])[-3:] if conversation_history else []
    
    # Detect conversation patterns
    if len(recent_exchanges) > 0:
        last_user_input = recent_exchanges[-1].get("prompt", "").lower()
        last_response = recent_exchanges[-1].get("response", "").lower()
        
        # Topic continuity detection
        topic_words = set(last_user_input.split()) & set(current_input.lower().split())
        if topic_words:
            return "continuation"  # User is continuing same topic
            
        # Question answering pattern
        if '?' in current_input and any(word in last_response for word in ["answer", "tell", "explain", "describe"]):
            return "followup_question"  # User asking for clarification
            
        # Shift to new topic
        return "topic_shift"
    
    return "new_conversation"


def capture_image_callback():
    """
    Optimized event handler that captures visual context only when likely needed.
    """
    global latest_captured_image_path
    print("📸 Optimized visual context capture triggered...")
    latest_captured_image_path = take_picture_from_tracker(face_tracker)

# Initialize Speech-to-Text (STT) Engine
stt_service = novastt.SpeechToText(on_record_start=capture_image_callback)

# Initialize Animatronic Control System (TTS & Servo Control)
robot = novatts.Animatronic()
robot.initialise(port_path=args.port)

# Initialize Computer Vision & Face Tracking System
face_tracker = novafacetrack.FaceTracker(command_callback=robot.queue_command, camera_index=SHARED_CAMERA_INDEX)


# --- BACKGROUND PROCESS MANAGEMENT ---

# Launch Face Tracking Thread
face_tracker.start()

# Launch Web Control Interface
web_interface = novaweb.WebInterface(stt_service, robot, face_tracker)
web_interface.start()

# Activate Audio Input Listener
stt_service.start_listener()

# Allow hardware stabilization
print("Initializing optical sensors...")
time.sleep(2)
print("✅ Nova AI System Online and Ready.")


# --- MAIN APPLICATION LOOP ---

print("\n" + "=" * 50)
print("Nova AI Robot - Independent InMoov Modification")
print("Press 'c' to communicate, 's' to stop.")
print("🌐 Web Dashboard: http://localhost:5000")
print("Press Ctrl+C to terminate system.")
print("=" * 50 + "\n")

# Process Long-Term Memory
novaresponse.long_term_memory_converter()

# Load Conversation Context
try:
    with open(config.CHAT_LOG_FILE, "r") as file:
        conversation_history = json.load(file)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Initializing fresh conversation history ({e}).")
    conversation_history = {"short_term": [], "long_term": [], "conversation": []}

# Compile Natural Language Understanding (NLU) Patterns
see_this_pattern = re.compile(r"(see this|look at|what do you see|describe this|what is that|what is in front|visual check|eyes|rate this|how does|what does|you see|can you see)", re.IGNORECASE)
visual_query_pattern = re.compile(r"#VISUAL", re.IGNORECASE)
search_query_pattern = re.compile(r"#SEARCH_QUERY", re.IGNORECASE)
fix_ai()

try:
    print("✅ System Active. Awaiting Input.")

    while True:
        try:
            # Process transcribed audio input
            if stt_service.transcribed_text:
                text = stt_service.transcribed_text.strip() if stt_service.transcribed_text is not None else ""
                
                if text == "#EXIT":
                    print("\n👋 Shutdown sequence initiated.")
                    break
                    
                print(f'\n🎤 User Input: "{text}"')
                
                # Analyze conversation flow
                conv_flow = conversation_flow_manager(text, conversation_history)
                print(f"🧠 Conversation Pattern: {conv_flow}")

                # Context-aware visual capture
                if smart_visual_capture(text):
                    print("🎯 Visual intent detected via smart filtering.")
                    
                    img_path = latest_captured_image_path
                    if not img_path:
                        print("⚠️ Visual buffer empty. Capturing real-time frame...")
                        img_path = take_picture_from_tracker(face_tracker)
                    else:
                        print(f"✅ Using buffered visual context: {img_path}")
                    
                    if img_path:
                        output = novaresponse.query_with_image(
                            text, conversation_history, image_path=img_path
                        )
                        if "not a visual query" in output.lower():
                            print("⚠️ Visual Analysis Rejection. Fallback to LLM.")
                            fallback_response = "Hmm, I'm having trouble focusing on that right now. Let me try a different approach."
                            robot.speak_text(fallback_response)
                            full_response_text = fallback_response
                        else:
                            robot.speak_text(output)
                            full_response_text = output
                    else:
                        fallback_response = "My vision system is having a bit of trouble at the moment."
                        robot.speak_text(fallback_response)
                        full_response_text = fallback_response

                    novaresponse.save_response(text, full_response_text or "")
                    conversation_history["conversation"].append(
                        {"prompt": text, "response": full_response_text or ""}
                    )
                    
                    latest_captured_image_path = None

                # 2. Standard Conversational Query (LLM Path)
                else:
                    full_response_text = novaresponse.response(text, conversation_history) or ""
                    
                    cleaned_response = full_response_text.strip().strip('"').strip("'").strip()
                    
                    print(f"🔍 LLM Output: '{cleaned_response}'")
                    
                    # Check for LLM-triggered Visual Query
                    if cleaned_response == "#VISUAL" or visual_query_pattern.search(cleaned_response):
                        print("🤖 LLM triggered internal visual query.")
                        
                        img_path = latest_captured_image_path
                        if not img_path:
                                print("⚠️ Visual buffer empty. Capturing real-time frame...")
                                img_path = take_picture_from_tracker(face_tracker)
                        else:
                            print(f"✅ Using buffered visual context: {img_path}")

                        if img_path:
                            output = novaresponse.query_with_image(
                                text, conversation_history, image_path=img_path
                            )
                            if "not a visual query" in output.lower():
                                print("⚠️ Visual Analysis Rejection. Fallback.")
                                fallback_response = "I'm having trouble focusing on that right now."
                                robot.speak_text(fallback_response)
                                full_response_text = fallback_response
                            else:
                                robot.speak_text(output)
                                full_response_text = output
                        else:
                            fallback_response = "My vision system is currently unresponsive."
                            robot.speak_text(fallback_response)
                            full_response_text = fallback_response
                            
                        latest_captured_image_path = None
                    
                    # Check for LLM-triggered Search Query
                    elif search_query_pattern.search(cleaned_response):
                            print("🔍 Real-time Information Retrieval triggered.")
                            search_result = novaresponse.search_response(text, conversation_history)
                            robot.speak_text(search_result)
                            full_response_text = search_result
                    
                    else:
                        robot.speak_text(full_response_text)

                    novaresponse.save_response(text, full_response_text or "")
                    conversation_history["conversation"].append(
                        {"prompt": text, "response": full_response_text or ""}
                    )
                    
                    latest_captured_image_path = None

            stt_service.transcribed_text = None
            print("\nListening for next interaction...")
            
            time.sleep(0.05)
            
        except Exception as e:
            print(f"\n❌ Runtime Exception: {e}")
            stt_service.transcribed_text = None
            time.sleep(1)

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n\n🛑 User Interrupt Detected.")

finally:
    # --- SYSTEM SHUTDOWN PROTOCOL ---
    print("Initiating system shutdown...")

    stt_service.stop_listener()
    face_tracker.stop()
    robot.shutdown()

    if face_tracker.is_alive():
        face_tracker.join(timeout=5)

    print("✅ Nova AI System Offline.")
