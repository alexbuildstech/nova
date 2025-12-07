#!/usr/bin/env python3
# animatronic_controller_v10_interactive_neck.py

import subprocess
import shutil
import time
import threading
import queue
import serial
import serial.tools.list_ports
import random
import re
from pynput import keyboard
from edge_tts import Communicate
from pydub import AudioSegment
from pydub.utils import make_chunks

class Animatronic:
    """
    This version adds an interactive feature: pressing the 'L' key during speech
    will send a command to center the neck without interrupting anything.
    It retains the direct connection and robust ACK flow control.
    """

    # --- Configuration (Synced with Arduino Code) ---
    VOICE = "en-US-GuyNeural"
    RATE = "+20%"  # FASTER SPEECH: Reduced playback time
    BAUD_RATE = 9600
    JAW_CLOSE_ANGLE = 30
    JAW_OPEN_ANGLES = [50, 80, 110]
    EYE_H_MIN, EYE_H_MID, EYE_H_MAX = 40, 80, 110
    EYE_V_MIN, EYE_V_MID, EYE_V_MAX = 70, 130, 180
    PAUSE_DURATION_COMMA, PAUSE_DURATION_FULLSTOP = 0.5, 0.5

    def __init__(self, specified_port=None):
        self._serial_port = None
        self._player_process = None
        self._key_listener = None
        self._command_queue = queue.PriorityQueue()
        self._events_queue = queue.Queue()
        self._stop_threads = threading.Event()
        self._is_speaking = threading.Event()
        self._audio_started = threading.Event()
        self._interrupted = threading.Event()  # Flag to signal full interruption
        self._player_command = self._get_player_command()
        self._specified_port = specified_port

    def queue_command(self, priority, command_str):
        """
        Allows external modules (like FaceTracker) to queue commands for the Arduino.
        priority: 1 (High/Speech), 2 (Low/Idle), etc.
        command_str: The command string (e.g., "neck 90")
        """
        self._command_queue.put((priority, command_str))

    def _open_port(self, device):
        """Attempt to open a specific serial device."""
        try:
            ser = serial.Serial(device, self.BAUD_RATE, timeout=1, write_timeout=1)
            print(f"✅ Port {device} opened successfully (manual selection).")
            time.sleep(2)  # Wait for Arduino reset
            return ser
        except (serial.SerialException, FileNotFoundError) as e:
            print(f"⚠️ Failed to open specified port {device}: {e}")
            return None

    def _find_arduino_port(self):
        """Connects to the first available serial port that doesn't throw an error, unless a specific port is set."""
        if self._specified_port:
            ser = self._open_port(self._specified_port)
            if ser:
                return ser
            # fall back to scanning if manual port failed
        ports = serial.tools.list_ports.comports()
        for port in ports:
            try:
                ser = serial.Serial(port.device, self.BAUD_RATE, timeout=1, write_timeout=1)
                print(f"✅ Port {port.device} opened successfully. Assuming it's the Animatronic.")
                time.sleep(2)  # IMPORTANT: Wait for the Arduino to reset
                return ser
            except (serial.SerialException, FileNotFoundError):
                continue
        print("❌ No working Arduino ports found. Please check connection.")
        return None

    def _get_player_command(self):
        if shutil.which("mpv"):
            return [
                "mpv",
                "--no-terminal",
                "--audio-buffer=0.2",
                "-"
            ]
        elif shutil.which("ffplay"): 
            return [
                "ffplay", 
                "-nodisp", 
                "-autoexit", 
                "-loglevel", "warning", 
                "-fflags", "nobuffer", 
                "-infbuf",
                "-probesize", "32768", 
                "-i", "-"
            ]
        elif shutil.which("mpg123"): return ["mpg123", "-q", "--buffer", "4096", "-"]
        else: raise RuntimeError("Install mpv, ffmpeg or mpg123 for audio playback.")

    def _start_interrupt_listener(self):
        """
        Starts a keyboard listener for the 'p' (interrupt) and 'l' (neck center) keys.
        """
        def on_press(key):
            try:
                # --- FEATURE: Interrupt Speech ---
                if key.char == 'p':
                    print("\n🛑 'p' pressed. Stopping audio.")
                    if self._player_process: self._player_process.terminate()
                    return False # Stops the listener

                # --- NEW FEATURE: Center Neck ---
                elif key.char == 'l':
                    print("\n▶️ 'l' pressed. Centering neck.")
                    # Add the command to the low-priority queue. Does not interrupt anything.
                    self._command_queue.put((2, "neck 70"))
                elif key.char == 'o':
                    print("\n▶️ 'o' pressed. Centering neck.")
                    # Add the command to the low-priority queue. Does not interrupt anything.
                    self._command_queue.put((2, "neck 120"))

            except AttributeError:
                # This handles special keys (Shift, Ctrl, etc.) which don't have a 'char' attribute
                pass

        self._key_listener = keyboard.Listener(on_press=on_press)
        self._key_listener.start()

    def _stop_interrupt_listener(self):
        if self._key_listener: self._key_listener.stop()

    def _serial_worker(self):
        """Sends commands from the queue and waits for an ACK ('K') from the Arduino."""
        print("Serial worker with ACK flow control started.")
        while not self._stop_threads.is_set():
            try:
                priority, command_str = self._command_queue.get(timeout=1)
                if self._serial_port and self._serial_port.is_open:
                    command = f"{command_str}\n".encode('utf-8')
                    self._serial_port.write(command)
                    ack = self._serial_port.readline().decode('utf-8').strip()
                    if ack != 'K':
                        print(f"⚠️ Bad ACK from Arduino: '{ack}' | Command: '{command_str}'")
                        self._serial_port.reset_input_buffer()
            except queue.Empty: continue
            except serial.SerialTimeoutException:
                print("!! SERIAL WRITE TIMEOUT !! Arduino unresponsive. Check connection.")
                time.sleep(1)
            except Exception as e:
                print(f"Critical error in serial_worker: {e}")
                break
        print("Serial worker thread stopped.")

    def _jaw_movement_generator(self):
        """
        Generates smoother, more organic jaw movements.
        Oscillates between open states while speaking, rather than fully closing every time.
        """
        current_angle = self.JAW_CLOSE_ANGLE
        
        while not self._stop_threads.is_set():
            self._is_speaking.wait(0.1)
            if not self._is_speaking.is_set(): 
                continue
            
            self._audio_started.wait()
            
            # Check for pause events (commas, full stops)
            try:
                event = self._events_queue.get_nowait()
                if "PAUSE" in event:
                    # Fully close on punctuation
                    self._command_queue.put((1, f"jaw {self.JAW_CLOSE_ANGLE}"))
                    current_angle = self.JAW_CLOSE_ANGLE
                    time.sleep(self.PAUSE_DURATION_COMMA if "COMMA" in event else self.PAUSE_DURATION_FULLSTOP)
                    continue
            except queue.Empty:
                pass

            if self._is_speaking.is_set():
                # Organic movement: Move to a random open position
                # Limit max opening to 90 to stay well under the 110 limit for safety
                target_open = random.uniform(50, 90)
                
                # Move to open position
                self._command_queue.put((1, f"jaw {int(target_open)}"))
                current_angle = target_open
                
                # Hold for a syllable duration (variable)
                time.sleep(random.uniform(0.1, 0.25))
                
                # Instead of fully closing, move to a "semi-closed" or "less open" position
                # This mimics continuous speech where the mouth doesn't always shut tight
                target_semi_closed = random.uniform(35, 45)
                self._command_queue.put((1, f"jaw {int(target_semi_closed)}"))
                current_angle = target_semi_closed
                
                # Short pause between syllables
                time.sleep(random.uniform(0.05, 0.15))

    def _perform_saccade(self, target_x, target_y):
        """
        Executes a realistic saccade with overshoot and micro-corrections.
        """
        # 1. Overshoot 1-2 degrees
        overshoot_x = target_x + random.uniform(1, 2) * random.choice([-1, 1])
        overshoot_y = target_y + random.uniform(1, 2) * random.choice([-1, 1])

        # Move instantly to overshoot
        self._command_queue.put((2, f"eye {int(overshoot_x)}"))
        self._command_queue.put((2, f"z {int(overshoot_y)}"))

        # 2. Short biological delay (20-40ms)
        time.sleep(random.uniform(0.02, 0.04))

        # 3. First correction (big)
        correction_x = target_x + random.uniform(0.5, 1.0) * random.choice([-1, 1])
        correction_y = target_y + random.uniform(0.5, 1.0) * random.choice([-1, 1])
        self._command_queue.put((2, f"eye {int(correction_x)}"))
        self._command_queue.put((2, f"z {int(correction_y)}"))

        time.sleep(random.uniform(0.02, 0.04))

        # 4. Final micro-correction (tiny)
        final_x = target_x + random.uniform(0.1, 0.2) * random.choice([-1, 1])
        final_y = target_y + random.uniform(0.1, 0.2) * random.choice([-1, 1])
        self._command_queue.put((2, f"eye {int(final_x)}"))
        self._command_queue.put((2, f"z {int(final_y)}"))

    def _eye_movement_generator(self):
        """Generates eye movements with LOW priority (2) using realistic saccades."""
        last_saccade_time = time.time()
        
        # State variables for natural behavior
        mode = "scanning" # scanning, examining, staring
        mode_change_time = time.time()
        current_focus_x = self.EYE_H_MID
        current_focus_y = self.EYE_V_MID
        
        while not self._stop_threads.is_set():
            current_time = time.time()
            
            # Randomly change modes every few seconds
            if current_time - mode_change_time > random.uniform(5.0, 15.0):
                mode = random.choice(["scanning", "examining", "staring"])
                mode_change_time = current_time
                # Pick a new focus point for examining/staring
                current_focus_x = random.randint(self.EYE_H_MIN + 20, self.EYE_H_MAX - 20)
                current_focus_y = random.randint(self.EYE_V_MIN + 20, self.EYE_V_MAX - 20)
            
            if self._is_speaking.is_set():
                # When talking, glance away occasionally but mostly look at "user" (center)
                if current_time - last_saccade_time > random.uniform(2.0, 5.0):
                    if random.random() < 0.7:
                        # Look at user (center-ish)
                        target_x = self.EYE_H_MID + random.randint(-10, 10)
                        target_y = self.EYE_V_MID + random.randint(-10, 10)
                    else:
                        # Glance away (thoughtful)
                        target_x = random.choice([self.EYE_H_MIN + 15, self.EYE_H_MAX - 15])
                        target_y = self.EYE_V_MID + random.randint(-20, 20)
                    
                    self._perform_saccade(target_x, target_y)
                    last_saccade_time = current_time
                else:
                    time.sleep(0.1)
            else:
                # IDLE BEHAVIOR
                
                # Determine dwell time based on mode
                if mode == "scanning":
                    dwell = random.uniform(0.3, 0.8) # Look around quickly
                elif mode == "examining":
                    dwell = random.uniform(0.8, 2.0) # Look at details
                else: # staring
                    dwell = random.uniform(2.0, 5.0) # Zone out
                
                if current_time - last_saccade_time > dwell:
                    if mode == "scanning":
                        # Big jumps across the range
                        target_x = random.randint(self.EYE_H_MIN, self.EYE_H_MAX)
                        target_y = random.randint(self.EYE_V_MIN, self.EYE_V_MAX)
                    
                    elif mode == "examining":
                        # Small jumps around a focus point
                        offset_x = random.randint(-15, 15)
                        offset_y = random.randint(-15, 15)
                        target_x = max(self.EYE_H_MIN, min(self.EYE_H_MAX, current_focus_x + offset_x))
                        target_y = max(self.EYE_V_MIN, min(self.EYE_V_MAX, current_focus_y + offset_y))
                    
                    else: # staring
                        # Very tiny micro-movements around focus
                        offset_x = random.randint(-5, 5)
                        offset_y = random.randint(-5, 5)
                        target_x = max(self.EYE_H_MIN, min(self.EYE_H_MAX, current_focus_x + offset_x))
                        target_y = max(self.EYE_V_MIN, min(self.EYE_V_MAX, current_focus_y + offset_y))

                    self._perform_saccade(target_x, target_y)
                    last_saccade_time = current_time
                else:
                    time.sleep(0.05)

    def _audio_streamer(self, text, player_process):
        try:
            for chunk in Communicate(text, self.VOICE, rate=self.RATE).stream_sync():
                if player_process.poll() is not None: 
                    print(f"❌ Player process died unexpectedly! Return code: {player_process.returncode}")
                    break
                if chunk["type"] == "audio" and chunk["data"]:
                    if not self._audio_started.is_set(): self._audio_started.set()
                    try:
                        player_process.stdin.write(chunk["data"])
                        player_process.stdin.flush() # Ensure data is sent immediately
                    except BrokenPipeError:
                        print("❌ Broken pipe: Player process closed stdin unexpectedly.")
                        break
                elif chunk["type"] == "WordBoundary":
                    if chunk["text"] == ",": self._events_queue.put("PAUSE_COMMA")
                    elif chunk["text"] == ".": self._events_queue.put("PAUSE_FULLSTOP")
        except Exception as e:
            print(f"Audio streaming error: {e}")
        finally:
            if player_process.stdin and not player_process.stdin.closed: player_process.stdin.close()

    def initialise(self, port_path=None):
        # Allow manual port override via argument or constructor-specified port
        if port_path:
            self._serial_port = self._open_port(port_path)
        else:
            self._serial_port = self._find_arduino_port()
        if not self._serial_port:
            print("⚠️ No Arduino found. Running in AUDIO-ONLY mode.")
        
        self._stop_threads.clear()
        threading.Thread(target=self._serial_worker, daemon=True).start()
        threading.Thread(target=self._jaw_movement_generator, daemon=True).start()
        threading.Thread(target=self._eye_movement_generator, daemon=True).start()
        return True

    def speak_text(self, text_to_speak):
        if not text_to_speak.strip(): return
        
        # Filter out emojis
        text_to_speak = re.sub(r'[\U00010000-\U0010ffff]', '', text_to_speak)
        
        print(f"▶️ Speaking: \"{text_to_speak}\" (Press 'p' to stop, 'l' to center neck)")
        self._command_queue.queue.clear()
        self._events_queue.queue.clear()
        self._audio_started.clear()
        self._is_speaking.set()
        self._start_interrupt_listener()

        try:

            # STREAMING PLAYBACK WITH REAL-TIME LIP SYNC
            try:
                # Start mpv process for streaming
                # --cache=yes --demuxer-max-bytes=128KiB minimizes buffering latency
                player_command = ["mpv", "--no-terminal", "--cache=yes", "--demuxer-max-bytes=128KiB", "-"]
                player_process = subprocess.Popen(
                    player_command, 
                    stdin=subprocess.PIPE, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
                self._player_process = player_process
                self._audio_started.set() # Signal eyes to be active

                # Stream chunks
                for chunk in Communicate(text_to_speak, self.VOICE, rate=self.RATE).stream_sync():
                    if not self._is_speaking.is_set(): 
                        player_process.terminate()
                        break
                        
                    if chunk["type"] == "audio" and chunk["data"]:
                        # 1. Write to player
                        try:
                            player_process.stdin.write(chunk["data"])
                            player_process.stdin.flush()
                        except BrokenPipeError:
                            break

                        # 2. Real-time Lip Sync (Approximate)
                        # Calculate RMS of this chunk
                        audio_segment = AudioSegment(
                            data=chunk["data"], 
                            sample_width=2, 
                            frame_rate=24000, # EdgeTTS default
                            channels=1
                        )
                        rms = audio_segment.rms
                        
                        # Map RMS to Jaw Angle
                        # Simple mapping: louder = wider
                        # Thresholds need tuning based on mic/speaker levels
                        if rms > 100: # Noise floor
                            # Normalize roughly (max RMS usually ~10000-20000 for TTS)
                            normalized = min(1.0, rms / 8000.0)
                            angle = 30 + (normalized * (90 - 30))
                            self._command_queue.put((1, f"jaw {int(angle)}"))
                        else:
                            self._command_queue.put((1, f"jaw {self.JAW_CLOSE_ANGLE}"))

                    elif chunk["type"] == "WordBoundary":
                        # Optional: Use word boundaries for finer control if needed
                        pass
                        
                # Close stdin to let mpv know stream is done
                if player_process.stdin:
                    player_process.stdin.close()
                
                # Wait for playback to finish
                player_process.wait()
                
            except Exception as e:
                print(f"❌ Error streaming audio: {e}")
                self._command_queue.put((1, f"jaw {self.JAW_CLOSE_ANGLE}"))
                    
        finally:
            # Small buffer to allow last jaw movements to finish naturally
            time.sleep(0.1) 
            
            self._is_speaking.clear()
            self._stop_interrupt_listener()

            self._command_queue.put((1, f"jaw {self.JAW_CLOSE_ANGLE}"))
            self._command_queue.put((2, f"eye {self.EYE_H_MID}"))
            self._command_queue.put((2, f"z {self.EYE_V_MID}"))
            print("✅ Speech complete.\n")

    def stop_speech(self):
        """Stops the current speech immediately and cancels pending stream."""
        print("\n🛑 External stop command received. Stopping audio.")
        self._interrupted.set() # Signal stream to stop
        if self._player_process:
            self._player_process.terminate()
        self._is_speaking.clear()

    def stream_text(self, text_generator):
        """
        Consumes a generator yielding text chunks.
        Buffers text into sentences and speaks them as they become available.
        """
        self._interrupted.clear() # Reset interrupt flag at start
        buffer = ""
        sentence_endings = re.compile(r'(?<=[.!?])\s+')
        full_text = ""
        
        # Fast start parameters
        MAX_BUFFER_SIZE = 60 # Characters
        
        for chunk in text_generator:
            if self._interrupted.is_set():
                print("⚠️ Stream interrupted. Stopping text processing.")
                break
                
            buffer += chunk
            full_text += chunk
            
            # Check for sentence endings
            sentences = sentence_endings.split(buffer)
            
            # If we have more than one part, the first parts are complete sentences
            if len(sentences) > 1:
                for sentence in sentences[:-1]:
                    if self._interrupted.is_set():
                        break
                    if sentence.strip():
                        self.speak_text(sentence.strip())
                
                # Keep the last part in the buffer
                buffer = sentences[-1]
            
            # FAST START / ANTI-STALL LOGIC
            # If buffer gets too long without a sentence end, force a split at comma or space
            elif len(buffer) > MAX_BUFFER_SIZE:
                # Try to split at last comma
                last_comma = buffer.rfind(',')
                if last_comma != -1:
                    to_speak = buffer[:last_comma+1] # Include comma
                    remaining = buffer[last_comma+1:]
                    if to_speak.strip():
                        self.speak_text(to_speak.strip())
                        buffer = remaining
                else:
                    # Try to split at last space
                    last_space = buffer.rfind(' ')
                    if last_space != -1:
                        to_speak = buffer[:last_space]
                        remaining = buffer[last_space+1:]
                        if to_speak.strip():
                            self.speak_text(to_speak.strip())
                            buffer = remaining
        
        # Speak any remaining text in the buffer
        if buffer.strip() and not self._interrupted.is_set():
            self.speak_text(buffer.strip())
            
        return full_text

    def shutdown(self):
        print("Shutting down...")
        self._stop_threads.set()
        self._stop_interrupt_listener()
        if self._serial_port and self._serial_port.is_open:
            time.sleep(0.5)
            self._serial_port.close()
        print("👋 Program ended.")

if __name__ == '__main__':
    skull = Animatronic()
    try:
        if skull.initialise():
            print("\n--- Animatronic Initialised with Direct Connection. ---")
            time.sleep(1)
            
            
            time.sleep(4)
            skull._command_queue.put((2, "neck 120"))
 
            skull._command_queue.put((2, "neck 80"))
            time.sleep(2)
            skull._command_queue.put((2, "neck 80"))
            skull.speak_text("That is easy. I simply hit 'Select All'… and then 'Delete'.")
            time.sleep(1)
            skull.speak_text("Would you like to confirm?")

          
    except Exception as e:
        print(f"A critical error occurred in the main block: {e}")
    finally:
        if skull:
            skull.shutdown()