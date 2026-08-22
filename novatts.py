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
import math  # For breathing rhythm calculations
from pynput import keyboard
from edge_tts import Communicate
from pydub import AudioSegment
import config

class Animatronic:
    """
    Enhanced animatronic controller with natural interruptions and unscripted movements.
    Features: Edge-case protected interruptions, random spontaneous movements, 
    debounced input handling, and graceful recovery mechanisms.
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
        self._emergency_interrupted = threading.Event()  # Emergency stop flag
        self._player_command = self._get_player_command()
        self._specified_port = specified_port
        
        # Interruption handling state
        self._last_interrupt_time = 0
        self._interrupt_debounce_ms = 300

    def queue_command(self, priority, command_str):
        """Allows external modules (like FaceTracker) to queue commands for the Arduino."""
        self._command_queue.put((priority, command_str))

    def _find_arduino_port(self):
        """Automatically detects Arduino by searching for common USB vendor IDs."""
        arduino_vids = {'2341', '2A03', '1A86', '10C4', '16C0', '03EB', '1366', '0483'}
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            if port.vid is not None:
                vid_hex = f"{port.vid:04X}"
                if vid_hex in arduino_vids:
                    print(f"[OK] Arduino detected on port: {port.device} ({port.description})")
                    return port.device
        return None

    def initialise(self, port_path=None):
        """Initializes serial connection and starts all worker threads."""
        print("--- Initializing Animatronic Control ---")
        
        # Determine port
        final_port = None
        if port_path:
            final_port = port_path
        elif self._specified_port:
            final_port = self._specified_port
        else:
            final_port = self._find_arduino_port()

        if final_port:
            try:
                self._serial_port = serial.Serial(final_port, self.BAUD_RATE, timeout=2)
                print(f"[OK] Serial connection established: {final_port}")
                time.sleep(2)  # Arduino reset delay
                self._serial_port.reset_input_buffer()
                print("Send 'STOP' to halt, 'L' for center neck.")
            except serial.SerialException as e:
                print(f"[ERROR] Serial error: {e}. Running in AUDIO-ONLY mode.")
                self._serial_port = None
        else:
            print("[WARNING] No Arduino found. Running in AUDIO-ONLY mode.")
        
        self._stop_threads.clear()
        threading.Thread(target=self._serial_worker, daemon=True).start()
        threading.Thread(target=self._jaw_movement_generator, daemon=True).start()
        threading.Thread(target=self._eye_movement_generator, daemon=True).start()
        threading.Thread(target=self._random_movement_generator, daemon=True).start()
        # Subconscious micro-movement threads for "alive" feeling
        threading.Thread(target=self._micro_saccade_generator, daemon=True).start()
        threading.Thread(target=self._breathing_rhythm_generator, daemon=True).start()
        threading.Thread(target=self._subconscious_twitch_generator, daemon=True).start()
        threading.Thread(target=self._natural_blink_generator, daemon=True).start()
        threading.Thread(target=self._idle_drift_generator, daemon=True).start()
        threading.Thread(target=self._attention_decay_generator, daemon=True).start()
        threading.Thread(target=self._emotional_micro_expression_generator, daemon=True).start()
        print("[OK] Subconscious micro-movement threads started (7 systems: micro-saccades, breathing, twitches, blinking, drift, attention, emotions)")
        return True

    def _serial_worker(self):
        """Optimized serial worker with command batching."""
        print("Optimized serial worker with batching started.")
        command_batch = []
        last_batch_time = time.time()
        batch_timeout = 0.016  # 16ms batching window
        
        while not self._stop_threads.is_set():
            try:
                priority, command_str = self._command_queue.get(timeout=1)
                
                if command_str.startswith(("x", "y", "z")):  # Servo commands can be batched
                    command_batch.append((priority, command_str))
                else:
                    # Send any pending batch first
                    if command_batch:
                        self._flush_command_batch(command_batch)
                        command_batch = []
                    
                    # Send urgent command immediately
                    if self._serial_port and self._serial_port.is_open:
                        command = f"{command_str}\n".encode('utf-8')
                        self._serial_port.write(command)
                        ack = self._serial_port.readline().decode('utf-8').strip()
                
                # Flush batch if timeout reached or batch is full
                current_time = time.time()
                if command_batch and (current_time - last_batch_time > batch_timeout or len(command_batch) >= 5):
                    self._flush_command_batch(command_batch)
                    command_batch = []
                    last_batch_time = current_time
                    
            except queue.Empty:
                # Flush any remaining commands on timeout
                if command_batch:
                    self._flush_command_batch(command_batch)
                    command_batch = []
                continue
            except Exception as e:
                print(f"Serial worker error: {e}")
                command_batch = []  # Clear batch on error

    def _flush_command_batch(self, command_batch):
        """Flush accumulated servo commands as a single batch."""
        if not command_batch or not self._serial_port or not self._serial_port.is_open:
            return
            
        # Sort by priority and create batch string
        command_batch.sort(key=lambda x: x[0])
        batch_string = "".join(f"{cmd}\n" for _, cmd in command_batch)
        
        try:
            self._serial_port.write(batch_string.encode('utf-8'))
            # Read single ACK for batch
            ack = self._serial_port.readline().decode('utf-8').strip()
            if ack != 'ACK':
                print(f"Batch ACK error: {ack}")
        except Exception as e:
            print(f"Batch flush error: {e}")

    def _start_interrupt_listener(self):
        """Enhanced interruption handler with edge case protection and debouncing."""
        def on_press(key):
            try:
                current_time = time.time() * 1000
                
                # Check debounce for regular interrupts
                if current_time - self._last_interrupt_time < self._interrupt_debounce_ms:
                    return None
                
                # Priority 1: Emergency stop (esc key)
                if hasattr(key, 'name') and key.name == 'esc':
                    print("\nEMERGENCY STOP - Immediately halting all operations")
                    self._emergency_interrupted.set()
                    self._interrupted.set()
                    if self._player_process: 
                        try:
                            self._player_process.kill()
                        except:
                            pass
                    # Reset to neutral position
                    self._command_queue.put((1, "x 85"))
                    self._command_queue.put((1, "z 120"))
                    self._command_queue.put((1, f"jaw {self.JAW_CLOSE_ANGLE}"))
                    return False
                
                # Priority 2: Conversation interrupt (space/p)
                if hasattr(key, 'char') and key.char in ['p', ' ']:
                    if self._is_speaking.is_set():
                        self._last_interrupt_time = current_time
                        print("\nConversation interrupted. Listening to user...")
                        self._interrupted.set()
                        
                        # Safe termination with timeout
                        if self._player_process: 
                            try:
                                self._player_process.terminate()
                                time.sleep(0.1)
                                if self._player_process.poll() is None:
                                    self._player_process.kill()
                            except Exception as e:
                                print(f"Interrupt error (handled): {e}")
                        
                        # Quick attention shift gesture
                        self._command_queue.put((1, "x 85"))
                        self._command_queue.put((1, "z 120"))
                        # Blink to show acknowledgment
                        self._command_queue.put((1, "blink 1"))
                    return None

                # Conversation gestures with debouncing
                if hasattr(key, 'char'):
                    if key.char == 'l':
                        print("\nLooking at you...")
                        self._command_queue.put((1, "x 85"))
                        self._command_queue.put((1, "z 120"))
                        self._command_queue.put((1, "y 88"))
                        
                    elif key.char == 'n':
                        print("\nPondering...")
                        self._command_queue.put((1, "x 95"))
                        self._command_queue.put((1, "z 100"))
                        self._command_queue.put((1, "jaw 40"))
                        
                    elif key.char == 'y':
                        print("\nAcknowledging...")
                        self._command_queue.put((1, "y 85"))
                        time.sleep(0.1)
                        self._command_queue.put((1, "y 88"))
                        self._command_queue.put((1, "x 80"))
                        self._command_queue.put((1, "z 115"))
                        
                    elif key.char == 'u':
                        print("\nUncertain...")
                        self._command_queue.put((1, "x 95"))
                        self._command_queue.put((1, "z 140"))
                        self._command_queue.put((1, "y 92"))

            except AttributeError:
                pass
            except Exception as e:
                print(f"Key handler error: {e}")
            
            return None

        self._key_listener = keyboard.Listener(on_press=on_press)
        self._key_listener.start()

    def _stop_interrupt_listener(self):
        if self._key_listener: 
            self._key_listener.stop()

    def _jaw_movement_generator(self):
        """Generates smoother, more organic jaw movements."""
        current_angle = self.JAW_CLOSE_ANGLE
        
        while not self._stop_threads.is_set():
            self._is_speaking.wait(0.1)
            
            if self._is_speaking.is_set() and not self._interrupted.is_set():
                # Choose an open target angle
                target_open = random.choice(self.JAW_OPEN_ANGLES)
                
                # Move to open position
                self._command_queue.put((1, f"jaw {target_open}"))
                current_angle = target_open
                
                # Hold for a syllable duration
                time.sleep(random.uniform(0.1, 0.25))
                
                # Move to semi-closed position
                target_semi_closed = random.uniform(35, 45)
                self._command_queue.put((1, f"jaw {int(target_semi_closed)}"))
                current_angle = target_semi_closed
                
                # Short pause between syllables
                time.sleep(random.uniform(0.05, 0.15))

    def _perform_saccade(self, target_x, target_y):
        """Executes a realistic saccade with overshoot and micro-corrections."""
        # Overshoot 1-2 degrees
        overshoot_x = target_x + random.uniform(1, 2) * random.choice([-1, 1])
        overshoot_y = target_y + random.uniform(1, 2) * random.choice([-1, 1])

        # Move instantly to overshoot
        self._command_queue.put((2, f"eye {int(overshoot_x)}"))
        self._command_queue.put((2, f"z {int(overshoot_y)}"))

        # Short biological delay
        time.sleep(random.uniform(0.02, 0.04))

        # First correction
        correction_x = target_x + random.uniform(0.5, 1.0) * random.choice([-1, 1])
        correction_y = target_y + random.uniform(0.5, 1.0) * random.choice([-1, 1])
        
        self._command_queue.put((2, f"eye {int(correction_x)}"))
        self._command_queue.put((2, f"z {int(correction_y)}"))
        
        time.sleep(random.uniform(0.02, 0.04))
        
        # Final correction to target
        self._command_queue.put((2, f"eye {int(target_x)}"))
        self._command_queue.put((2, f"z {int(target_y)}"))

    def _eye_movement_generator(self):
        """Generates eye movements with realistic saccades and unscripted movements."""
        last_saccade_time = time.time()
        last_unscripted_time = time.time()
        unscripted_cooldown = random.uniform(8.0, 20.0)
        
        # State variables
        mode = "scanning"
        mode_change_time = time.time()
        current_focus_x = self.EYE_H_MID
        current_focus_y = self.EYE_V_MID
        
        # Unscripted movement patterns
        unscripted_patterns = [
            "double_take", "slow_drift", "micro_tremor", 
            "blink_look", "thoughtful_gaze", "surprise_glance"
        ]
        
        while not self._stop_threads.is_set():
            current_time = time.time()
            
            # Trigger unscripted movement occasionally
            if (current_time - last_unscripted_time > unscripted_cooldown and 
                not self._is_speaking.is_set() and
                random.random() < 0.3):
                
                pattern = random.choice(unscripted_patterns)
                self._execute_unscripted_movement(pattern)
                last_unscripted_time = current_time
                unscripted_cooldown = random.uniform(8.0, 20.0)
                last_saccade_time = current_time
                continue
            
            # Randomly change modes
            if current_time - mode_change_time > random.uniform(5.0, 15.0):
                mode = random.choice(["scanning", "examining", "staring"])
                mode_change_time = current_time
                current_focus_x = random.randint(self.EYE_H_MIN + 20, self.EYE_H_MAX - 20)
                current_focus_y = random.randint(self.EYE_V_MIN + 20, self.EYE_V_MAX - 20)
            
            if self._is_speaking.is_set():
                if current_time - last_saccade_time > random.uniform(2.0, 5.0):
                    if random.random() < 0.7:
                        target_x = self.EYE_H_MID + random.randint(-10, 10)
                        target_y = self.EYE_V_MID + random.randint(-10, 10)
                    else:
                        target_x = random.choice([self.EYE_H_MIN + 15, self.EYE_H_MAX - 15])
                        target_y = self.EYE_V_MID + random.randint(-20, 20)
                    
                    self._perform_saccade(target_x, target_y)
                    last_saccade_time = current_time
                else:
                    time.sleep(0.1)
            else:
                # IDLE BEHAVIOR
                if mode == "scanning":
                    dwell = random.uniform(0.3, 0.8)
                elif mode == "examining":
                    dwell = random.uniform(0.8, 2.0)
                else:
                    dwell = random.uniform(2.0, 5.0)
                
                if current_time - last_saccade_time > dwell:
                    if mode == "scanning":
                        target_x = random.randint(self.EYE_H_MIN, self.EYE_H_MAX)
                        target_y = random.randint(self.EYE_V_MIN, self.EYE_V_MAX)
                    elif mode == "examining":
                        offset_x = random.randint(-15, 15)
                        offset_y = random.randint(-15, 15)
                        target_x = max(self.EYE_H_MIN, min(self.EYE_H_MAX, current_focus_x + offset_x))
                        target_y = max(self.EYE_V_MIN, min(self.EYE_V_MAX, current_focus_y + offset_y))
                    else:
                        offset_x = random.randint(-5, 5)
                        offset_y = random.randint(-5, 5)
                        target_x = max(self.EYE_H_MIN, min(self.EYE_H_MAX, current_focus_x + offset_x))
                        target_y = max(self.EYE_V_MIN, min(self.EYE_V_MAX, current_focus_y + offset_y))

                    self._perform_saccade(target_x, target_y)
                    last_saccade_time = current_time
                else:
                    time.sleep(0.05)

    def _execute_unscripted_movement(self, pattern):
        """Execute spontaneous, unscripted movements for natural 'alive' behavior."""
        try:
            if pattern == "double_take":
                self._command_queue.put((2, "x 45"))
                time.sleep(0.08)
                self._command_queue.put((2, "x 125"))
                time.sleep(0.15)
                self._command_queue.put((2, "x 85"))
                
            elif pattern == "slow_drift":
                drift_direction = random.choice([-1, 1])
                for i in range(5):
                    x = 85 + (drift_direction * i * 8)
                    self._command_queue.put((2, f"x {max(40, min(130, x))}"))
                    time.sleep(0.3)
                for i in range(5, -1, -1):
                    x = 85 + (drift_direction * i * 8)
                    self._command_queue.put((2, f"x {max(40, min(130, x))}"))
                    time.sleep(0.2)
                    
            elif pattern == "micro_tremor":
                base_x, base_y = 85, 130
                for _ in range(8):
                    offset_x = random.randint(-3, 3)
                    offset_y = random.randint(-2, 2)
                    self._command_queue.put((2, f"x {base_x + offset_x}"))
                    self._command_queue.put((2, f"z {base_y + offset_y}"))
                    time.sleep(0.05)
                    
            elif pattern == "blink_look":
                self._command_queue.put((2, "blink 1"))
                time.sleep(0.1)
                target_x = random.randint(self.EYE_H_MIN + 10, self.EYE_H_MAX - 10)
                target_y = random.randint(self.EYE_V_MIN + 10, self.EYE_V_MAX - 10)
                self._command_queue.put((2, f"x {target_x}"))
                self._command_queue.put((2, f"z {target_y}"))
                
            elif pattern == "thoughtful_gaze":
                self._command_queue.put((2, "x 95"))
                self._command_queue.put((2, "z 90"))
                time.sleep(0.5)
                for _ in range(4):
                    self._command_queue.put((2, f"x {95 + random.randint(-2, 2)}"))
                    time.sleep(0.2)
                    
            elif pattern == "surprise_glance":
                self._command_queue.put((2, "x 40"))
                self._command_queue.put((2, "z 160"))
                time.sleep(0.15)
                self._command_queue.put((2, "x 130"))
                self._command_queue.put((2, "z 70"))
                time.sleep(0.1)
                self._command_queue.put((2, "x 85"))
                self._command_queue.put((2, "z 130"))
                
        except Exception as e:
            print(f"Unscripted movement error (non-critical): {e}")

    def _random_movement_generator(self):
        """Additional random micro-movements for continuous 'alive' feel."""
        while not self._stop_threads.is_set():
            time.sleep(random.uniform(3.0, 8.0))  # Random interval
            
            if not self._is_speaking.is_set() and not self._interrupted.is_set():
                # Random micro-adjustments
                if random.random() < 0.4:  # 40% chance
                    micro_x = 85 + random.randint(-5, 5)
                    micro_y = 130 + random.randint(-3, 3)
                    self._command_queue.put((3, f"x {micro_x}"))
                    self._command_queue.put((3, f"z {micro_y}"))

    def _audio_streamer(self, text, player_process):
        """Streams audio with lip sync."""
        try:
            for chunk in Communicate(text, self.VOICE, rate=self.RATE).stream_sync():
                if player_process.poll() is not None: 
                    break
                if self._interrupted.is_set() or self._emergency_interrupted.is_set():
                    break
                    
                if chunk.get("type") == "audio" and chunk.get("data"):
                    try:
                        player_process.stdin.write(chunk["data"])
                        player_process.stdin.flush()
                    except BrokenPipeError:
                        break

                    # Lip sync
                    try:
                        audio_segment = AudioSegment(
                            data=chunk["data"], 
                            sample_width=2, 
                            frame_rate=24000,
                            channels=1
                        )
                        rms = audio_segment.rms
                        if rms > 100:
                            normalized = min(1.0, rms / 8000.0)
                            angle = 30 + (normalized * 60)
                            self._command_queue.put((1, f"jaw {int(angle)}"))
                        else:
                            self._command_queue.put((1, f"jaw {self.JAW_CLOSE_ANGLE}"))
                    except:
                        pass

        except Exception as e:
            print(f"Audio streamer error: {e}")

    def speak_text(self, text_to_speak):
        """Natural speech with conversational pacing and gestures."""
        if not text_to_speak or not text_to_speak.strip():
            return
        
        # Filter out emojis
        text_to_speak = re.sub(r'[\U00010000-\U0010ffff]', '', text_to_speak)
        
        print(f"Speaking: \"{text_to_speak}\"")
        print("   [Press: SPACE/p=interrupt, ESC=emergency, l/n/y/u=gestures]")
        
        self._command_queue.queue.clear()
        self._events_queue.queue.clear()
        self._audio_started.clear()
        self._interrupted.clear()
        self._emergency_interrupted.clear()
        self._is_speaking.set()
        self._start_interrupt_listener()

        try:
            # Pre-speech attention gesture
            self._command_queue.put((1, "x 80"))
            self._command_queue.put((1, "z 120"))
            
            # Start player
            player_command = ["mpv", "--no-terminal", "--cache=no", "--demuxer-max-bytes=32KiB", "--untimed", "-"]
            player_process = subprocess.Popen(
                player_command, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            self._player_process = player_process
            self._audio_started.set()

            # Stream audio
            self._audio_streamer(text_to_speak, player_process)
            
            # Cleanup
            if player_process.poll() is None:
                try:
                    player_process.stdin.close()
                    player_process.wait(timeout=1)
                except:
                    player_process.kill()
                    
        except Exception as e:
            print(f"Error in speak_text: {e}")
            
        finally:
            self._is_speaking.clear()
            self._stop_interrupt_listener()
            self._command_queue.put((2, f"z {self.EYE_V_MID}"))
            self._command_queue.put((1, f"jaw {self.JAW_CLOSE_ANGLE}"))
            print("[OK] Speech complete.\n")

    def stop_speech(self):
        """Enhanced speech stop with edge case handling and graceful recovery."""
        print("\nStop command received. Gracefully halting speech...")
        
        self._interrupted.set()
        self._emergency_interrupted.set()
        
        # Graceful termination with fallback
        if self._player_process:
            try:
                self._player_process.terminate()
                time.sleep(0.15)
                if self._player_process.poll() is None:
                    print("[WARNING] Force killing stuck audio process...")
                    self._player_process.kill()
                    time.sleep(0.05)
            except Exception as e:
                print(f"Audio stop error (handled): {e}")
        
        self._is_speaking.clear()
        self._command_queue.put((1, f"jaw {self.JAW_CLOSE_ANGLE}"))
        
        # Recovery pause
        time.sleep(config.INTERRUPT_RECOVERY_TIME)
        
        self._interrupted.clear()
        self._emergency_interrupted.clear()
        print("[OK] Ready for next interaction.")

    def stream_text(self, text_generator):
        """Consumes a generator yielding text chunks with natural buffering."""
        self._interrupted.clear()
        buffer = ""
        sentence_endings = re.compile(r'(?<=[.!?])\s+')
        MAX_BUFFER_SIZE = 60
        
        for chunk in text_generator:
            if self._interrupted.is_set():
                print("[WARNING] Stream interrupted. Stopping text processing.")
                break
                
            buffer += chunk
            
            sentences = sentence_endings.split(buffer)
            
            if len(sentences) > 1:
                for sentence in sentences[:-1]:
                    if self._interrupted.is_set():
                        break
                    if sentence.strip():
                        self.speak_text(sentence.strip())
                buffer = sentences[-1]
            
            elif len(buffer) > MAX_BUFFER_SIZE:
                last_comma = buffer.rfind(',')
                last_space = buffer.rfind(' ')
                split_point = last_comma if last_comma > len(buffer) * 0.6 else last_space
                
                if split_point > 10:
                    self.speak_text(buffer[:split_point].strip())
                    buffer = buffer[split_point:].strip()
        
        if buffer.strip() and not self._interrupted.is_set():
            self.speak_text(buffer.strip())

    # ============================================================================
    # SUBCONSCIOUS MICRO-MOVEMENT GENERATORS
    # These create an "alive" feeling without being consciously noticeable
    # ============================================================================
    
    def _micro_saccade_generator(self):
        """
        Micro-saccades: Tiny involuntary eye movements that occur even when staring.
        Humans make these constantly (every ~200ms) but they're barely perceptible.
        This prevents the "dead stare" effect of fixed eyes.
        """
        print("Micro-saccade generator started (subconscious eye movements)")
        base_x, base_y = 85, 130
        
        while not self._stop_threads.is_set():
            time.sleep(config.MICRO_SACCADE_INTERVAL)
            
            # Only when not speaking and not already moving significantly
            if not self._is_speaking.is_set():
                # Generate tiny random offsets (±2 degrees)
                micro_x = base_x + random.randint(-config.MICRO_SACCADE_SIZE, config.MICRO_SACCADE_SIZE)
                micro_y = base_y + random.randint(-config.MICRO_SACCADE_SIZE//2, config.MICRO_SACCADE_SIZE//2)
                
                # Apply with lowest priority (4) so it doesn't conflict
                self._command_queue.put((4, f"x {micro_x}"))
                self._command_queue.put((4, f"z {micro_y}"))
                
                # Slowly drift base position to prevent repetitive patterns
                base_x += random.uniform(-0.5, 0.5)
                base_y += random.uniform(-0.3, 0.3)
                base_x = max(75, min(95, base_x))  # Keep within subtle range
                base_y = max(125, min(135, base_y))
    
    def _breathing_rhythm_generator(self):
        """
        Simulates breathing through subtle head/neck movement.
        Creates a rhythmic, life-like motion that humans subconsciously expect.
        Cycle: 4 seconds (inhale/exhale pattern)
        """
        print("Breathing rhythm generator started")
        breath_phase = 0.0  # 0 to 2π
        
        while not self._stop_threads.is_set():
            # Calculate breathing offset (sine wave)
            breath_offset = math.sin(breath_phase) * config.BREATHING_AMPLITUDE
            
            # Apply to neck/head position (y-axis for subtle nod)
            # Only when not speaking to avoid conflict
            if not self._is_speaking.is_set():
                neck_pos = 88 + breath_offset
                self._command_queue.put((4, f"y {int(neck_pos)}"))
            
            # Advance phase
            breath_phase += (2 * math.pi) / (config.BREATHING_CYCLE * 60)  # Assuming 60 iterations/sec
            if breath_phase > 2 * math.pi:
                breath_phase = 0
            
            time.sleep(0.016)  # ~60 FPS
    
    def _subconscious_twitch_generator(self):
        """
        Occasional micro-twitches that real humans have.
        Small, quick movements that suggest neural activity and muscle tone.
        Happens randomly every ~30-50 seconds on average.
        """
        print("Subconscious twitch generator started")
        
        while not self._stop_threads.is_set():
            # Random check every second
            time.sleep(1.0)
            
            if random.random() < config.SUBCONSCIOUS_TWITCH_CHANCE:
                if not self._is_speaking.is_set():
                    # Pick a random servo and twitch it slightly
                    twitch_type = random.choice(['eye_x', 'eye_y', 'neck', 'jaw'])
                    
                    if twitch_type == 'eye_x':
                        current = 85 + random.randint(-3, 3)
                        self._command_queue.put((4, f"x {current}"))
                        time.sleep(0.08)
                        self._command_queue.put((4, f"x {85}"))
                    
                    elif twitch_type == 'eye_y':
                        current = 130 + random.randint(-2, 2)
                        self._command_queue.put((4, f"z {current}"))
                        time.sleep(0.06)
                        self._command_queue.put((4, f"z {130}"))
                    
                    elif twitch_type == 'neck':
                        current = 88 + random.randint(-2, 2)
                        self._command_queue.put((4, f"y {current}"))
                        time.sleep(0.1)
                        self._command_queue.put((4, f"y {88}"))
    
    def _natural_blink_generator(self):
        """
        Natural blinking with human-like patterns.
        - Blink rate varies (not mechanical)
        - Double-blinks occasionally (tired/dry eyes)
        - Longer blinks when "thinking"
        - Cluster blinks (several in short succession)
        """
        print("Natural blink generator started")
        
        while not self._stop_threads.is_set():
            # Random interval between blinks (2.5 to 6 seconds)
            interval = random.uniform(config.BLINK_MIN_INTERVAL, config.BLINK_MAX_INTERVAL)
            time.sleep(interval)
            
            if not self._is_speaking.is_set():
                blink_type = random.random()
                
                if blink_type < 0.05:  # 5% chance of double-blink
                    # Double blink (like when eyes are dry)
                    self._command_queue.put((3, "blink 1"))
                    time.sleep(0.18)
                    self._command_queue.put((3, "blink 1"))
                
                elif blink_type < 0.15:  # 10% chance of "thinking" blink (longer)
                    # Extended blink (processing/thinking)
                    self._command_queue.put((3, "blink 1"))
                    time.sleep(0.25)
                
                elif blink_type < 0.20:  # 5% chance of blink cluster
                    # Rapid blinks (3 in succession)
                    for _ in range(3):
                        self._command_queue.put((3, "blink 1"))
                        time.sleep(0.12)
                
                else:  # 80% normal blink
                    self._command_queue.put((3, "blink 1"))
    
    def _idle_drift_generator(self):
        """
        Slow drift when idle - eyes naturally drift around even when "focused".
        Prevents the statue-like frozen stare.
        Speed: ~0.3 degrees per second (very slow, barely perceptible)
        """
        print("Idle drift generator started")
        
        drift_x, drift_y = 85, 130
        target_x, target_y = 85, 130
        
        while not self._stop_threads.is_set():
            time.sleep(0.1)
            
            if not self._is_speaking.is_set():
                # Pick new target occasionally
                if random.random() < 0.02:  # 2% chance per 100ms
                    target_x = random.randint(80, 90)
                    target_y = random.randint(125, 135)
                
                # Drift toward target slowly
                if abs(drift_x - target_x) > 0.5:
                    drift_x += (target_x - drift_x) * config.IDLE_DRIFT_SPEED * 0.1
                if abs(drift_y - target_y) > 0.5:
                    drift_y += (target_y - drift_y) * config.IDLE_DRIFT_SPEED * 0.1
                
                self._command_queue.put((4, f"x {int(drift_x)}"))
                self._command_queue.put((4, f"z {int(drift_y)}"))
    
    def _attention_decay_generator(self):
        """
        Simulates attention decay - when idle, attention slowly wanders.
        Creates micro-movements suggesting the robot is "alive" and aware.
        Movement gets more random over time when idle.
        """
        print("Attention decay generator started")
        
        idle_time = 0
        base_x, base_y = 85, 130
        
        while not self._stop_threads.is_set():
            time.sleep(0.5)
            
            if not self._is_speaking.is_set():
                idle_time += 0.5
                
                # Attention wanders more the longer we're idle
                wander_factor = min(idle_time * config.ATTENTION_DECAY_RATE, 5.0)
                
                # Add wandering to base position
                wander_x = base_x + random.gauss(0, wander_factor)
                wander_y = base_y + random.gauss(0, wander_factor * 0.6)
                
                # Constrain to reasonable limits
                wander_x = max(70, min(100, wander_x))
                wander_y = max(120, min(140, wander_y))
                
                self._command_queue.put((4, f"x {int(wander_x)}"))
                self._command_queue.put((4, f"z {int(wander_y)}"))
            else:
                # Reset idle time when speaking
                idle_time = 0

    def _emotional_micro_expression_generator(self):
        """
        Subconscious emotional micro-expressions that leak through.
        These are tiny facial movements that happen when processing information
        or reacting emotionally, even when trying to maintain a neutral expression.
        - Subtle eyebrow raises (surprise/interest)
        - Tiny squints (processing/concentration)
        - Micro-nods (agreement/understanding)
        - Slight head tilts (curiosity)
        """
        print("Emotional micro-expression generator started")
        
        expression_cooldown = 0
        
        while not self._stop_threads.is_set():
            time.sleep(0.5)
            expression_cooldown -= 0.5
            
            if not self._is_speaking.is_set() and expression_cooldown <= 0:
                # Random chance of micro-expression (3% per second)
                if random.random() < 0.015:  # 1.5% per 500ms = ~3% per second
                    expression = random.choice([
                        'subtle_surprise', 'processing_squint', 'micro_nod', 
                        'curiosity_tilt', 'thoughtful_look'
                    ])
                    
                    if expression == 'subtle_surprise':
                        # Quick eyebrow raise (eyes widen slightly)
                        self._command_queue.put((3, "z 125"))
                        time.sleep(0.1)
                        self._command_queue.put((3, "z 130"))
                        expression_cooldown = 4.0
                    
                    elif expression == 'processing_squint':
                        # Brief squint (processing something)
                        self._command_queue.put((3, "x 87"))  # Slight convergence
                        self._command_queue.put((3, "z 132"))
                        time.sleep(0.15)
                        self._command_queue.put((3, "x 85"))
                        self._command_queue.put((3, "z 130"))
                        expression_cooldown = 3.0
                    
                    elif expression == 'micro_nod':
                        # Tiny nod (agreement/understanding)
                        self._command_queue.put((3, "y 87"))
                        time.sleep(0.08)
                        self._command_queue.put((3, "y 88"))
                        time.sleep(0.08)
                        self._command_queue.put((3, "y 87"))
                        expression_cooldown = 5.0
                    
                    elif expression == 'curiosity_tilt':
                        # Head tilt (curious about something)
                        self._command_queue.put((3, "y 90"))
                        time.sleep(0.5)  # Hold the tilt
                        self._command_queue.put((3, "y 88"))
                        expression_cooldown = 6.0
                    
                    elif expression == 'thoughtful_look':
                        # Eyes drift up while thinking
                        self._command_queue.put((3, "x 88"))
                        self._command_queue.put((3, "z 125"))
                        time.sleep(0.3)
                        self._command_queue.put((3, "x 85"))
                        self._command_queue.put((3, "z 130"))
                        expression_cooldown = 4.0

    def _get_player_command(self):
        """Detects available audio player command."""
        if shutil.which("mpv"): 
            return ["mpv", "--no-terminal", "--quiet", "-"]
        elif shutil.which("ffplay"): 
            return [
                "ffplay", "-v", "0", "-nodisp", "-autoexit", 
                "-fflags", "nobuffer", "-infbuf", "-probesize", "32768", "-i", "-"
            ]
        elif shutil.which("mpg123"): 
            return ["mpg123", "-q", "--buffer", "4096", "-"]
        else: 
            raise RuntimeError("Install mpv, ffmpeg or mpg123 for audio playback.")

    def shutdown(self):
        """Stops all threads and closes serial connection."""
        print("Shutting down Animatronic...")
        self._stop_threads.set()
        self._interrupted.set()
        self._emergency_interrupted.set()
        
        if self._player_process:
            try:
                self._player_process.kill()
            except:
                pass
                
        if self._key_listener:
            self._key_listener.stop()
            
        if self._serial_port and self._serial_port.is_open:
            self._serial_port.close()
            
        time.sleep(0.5)
        print("[OK] Animatronic shutdown complete.")