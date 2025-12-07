# novafacetracker.py

import cv2
import serial
import time
import serial.tools.list_ports
import threading
import numpy as np
import queue
import config

class FaceTracker(threading.Thread):
    def __init__(self, command_callback=None, camera_index=4, baud_rate=9600):
        super().__init__()
        self.daemon = True
        self.command_callback = command_callback

        # --- Constants & Configuration ---
        self.BAUD_RATE = baud_rate
        self.CAMERA_INDEX = camera_index
        self.MIN_ANGLE = config.SERVO_MIN_ANGLE
        self.MAX_ANGLE = config.SERVO_MAX_ANGLE
        self.MIN_SERVO_ANGLE_CHANGE = 3
        self.CONFIDENCE_THRESHOLD = config.CONFIDENCE_THRESHOLD
        self.DETECTION_INTERVAL = 0.01

        # --- Vertical Eye Movement Config (THE "ABSOLUTE CINEMA" VERSION) ---
        self.EYE_V_MIN = config.EYE_V_MIN  # Angle for when face is CLOSE (more downward gaze)
        self.EYE_V_MID = config.EYE_V_MID
        self.EYE_V_MAX = config.EYE_V_MAX # Angle for when face is FAR

        # --- Dead zones ---
        self.HORIZONTAL_DEAD_ZONE_PERCENT = 0.15
        
        # --- Depth Compensation (Dynamic Speed & Z-Axis) Config (RECALIBRATED) ---
        self.MIN_STEP_CLOSE = 2.0
        self.MAX_STEP_FAR = 8.0
        self.MIN_FACE_WIDTH_SCALE = 80   # Represents a face that is FAR
        self.MAX_FACE_WIDTH_SCALE = 220  # Represents a face that is CLOSE

        # --- Frame sharing and threading ---
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.last_known_face_box = None
        self.box_lock = threading.Lock()
        
        # --- Queues for Inter-thread Communication ---
        self.detection_frame_queue = queue.Queue(maxsize=1)
        self.camera_output_queue = queue.Queue(maxsize=1)

        # --- Serial and Model Loading ---
        # self.ser = self._find_arduino_port()  <-- REMOVED
        print("ℹ️ Loading DNN Face Detector model...")
        self.net = cv2.dnn.readNetFromCaffe(
            config.PROTOTXT_PATH, config.CAFFEMODEL_PATH
        )
        print("✅ DNN Model Loaded.")

        # --- State Variables ---
        self.NEUTRAL_ANGLE = 80
        self.target_angle = self.NEUTRAL_ANGLE
        self.current_angle = self.NEUTRAL_ANGLE
        self.last_sent_angle = -999
        self.target_eye_v_angle = self.EYE_V_MID
        self.current_eye_v_angle = self.EYE_V_MID
        self.last_sent_eye_v_angle = -999
        self.dynamic_max_angle_step = self.MAX_STEP_FAR
        self.running = False

    def get_latest_frame(self):
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
        return None


    def _map_value(self, value, in_min, in_max, out_min, out_max):
        value = max(in_min, min(value, in_max))
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def _open_camera(self, index):
        """Attempt to open a camera at the given index, fallback to subsequent indices up to 5.
        Returns a cv2.VideoCapture object if successful, otherwise None.
        """
        max_tries = 5
        for i in range(max_tries):
            try_idx = index + i
            cap = cv2.VideoCapture(try_idx)
            if cap.isOpened():
                print(f"✅ [FaceTracker] Camera opened at index {try_idx}.")

        # Servo Motor Constraints
        self.MIN_ANGLE = config.SERVO_MIN_ANGLE
        self.MAX_ANGLE = config.SERVO_MAX_ANGLE
        
        # Initial Servo Positions (Centered)
        self.current_x_angle = 90
        self.current_y_angle = 90
        
        # Eye Mechanism Constraints
        self.EYE_V_MIN = config.EYE_V_MIN
        self.EYE_V_MID = config.EYE_V_MID
        self.EYE_V_MAX = config.EYE_V_MAX

    def run(self):
        """
        Main execution loop for the Vision Thread.
        Captures video, processes frames, and calculates servo trajectories.
        """
        print(f"📷 Initializing Vision System on Camera Index {self.camera_index}...")
        self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            print("❌ Vision System Failure: Camera not detected.")
            return

        # Optimize Camera Settings for Low Latency
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            # Update Frame Buffer (Thread-Safe)
            with self.lock:
                self.latest_frame = frame.copy()

            # Pre-process frame for DNN Inference
            (h, w) = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                (300, 300), (104.0, 177.0, 123.0))

            self.net.setInput(blob)
            detections = self.net.forward()

            face_found = False
            
            # Iterate through detections to find the most prominent face
            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]

                if confidence > 0.5:
                    face_found = True
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")

                    # Calculate Face Centroid
                    face_center_x = (startX + endX) // 2
                    face_center_y = (startY + endY) // 2
                    
                    # Calculate Frame Center
                    frame_center_x = w // 2
                    frame_center_y = h // 2

                    # Calculate Error Deltas
                    error_x = face_center_x - frame_center_x
                    error_y = face_center_y - frame_center_y

                    # Proportional Control Logic (Simple P-Controller)
                    if abs(error_x) > 20:
                        self.current_x_angle -= error_x * 0.05
                    if abs(error_y) > 20:
                        self.current_y_angle += error_y * 0.05

                    # Clamp Servo Angles to Safe Limits
                    self.current_x_angle = max(self.MIN_ANGLE, min(self.MAX_ANGLE, self.current_x_angle))
                    self.current_y_angle = max(self.MIN_ANGLE, min(self.MAX_ANGLE, self.current_y_angle))

                    # Dispatch Servo Commands
                    # X-axis controls Head Rotation (Neck)
                    self.command_callback(f"S0:{int(self.current_x_angle)}")
                    
                    # Y-axis controls Eye Vertical Movement (Eyelids/Eyeballs)
                    # Map Y-angle to Eye Servo Range
                    eye_angle = np.interp(self.current_y_angle, [self.MIN_ANGLE, self.MAX_ANGLE], [self.EYE_V_MIN, self.EYE_V_MAX])
                    self.command_callback(f"S1:{int(eye_angle)}")
                    
                    # Break after tracking the primary face
                    break

            time.sleep(0.03)

        self.cap.release()
        print("📷 Vision System Deactivated.")

    def get_latest_frame(self):
        """
        Retrieves the most recent frame from the buffer.
        Thread-safe access for external visual analysis.
        """
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None

    def stop(self):
        """
        Signals the thread to terminate gracefully.
        """
        self.running = False

            with self.box_lock:
                 # Update the box if a face is found, otherwise it holds the last good box
                self.last_known_face_box = best_face_box if found_face_this_frame else self.last_known_face_box

            time.sleep(self.DETECTION_INTERVAL)

    def run(self):
        self.running = True

        detector_thread = threading.Thread(target=self._face_detection_loop, daemon=True)
        detector_thread.start()
        
        camera_thread = threading.Thread(target=self._camera_reader_loop, daemon=True)
        camera_thread.start()
        
        print("✅ Face tracker is running.")
        
        while self.running:
            try:
                frame = self.camera_output_queue.get(timeout=1)
            except queue.Empty:
                print("⚠️ Camera feed timed out.")
                continue

            with self.frame_lock:
                self.latest_frame = frame
            
            if not self.detection_frame_queue.full():
                self.detection_frame_queue.put(frame.copy())

            with self.box_lock:
                box = self.last_known_face_box
            if box is not None:
                (startX, startY, endX, endY) = box
                # cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 255, 0), 2) # DISABLED: Prevents AI from seeing the green box

            # --- Servo Logic ---
            # Calculate base servo angles from tracking
            delta_angle = self.target_angle - self.current_angle
            step = max(-self.dynamic_max_angle_step, min(self.dynamic_max_angle_step, delta_angle))
            if abs(delta_angle) > 1: self.current_angle += step
            
            delta_eye_v = self.target_eye_v_angle - self.current_eye_v_angle
            step_eye_v = max(-self.dynamic_max_angle_step, min(self.dynamic_max_angle_step, delta_eye_v))
            if abs(delta_eye_v) > 1: self.current_eye_v_angle += step_eye_v

            # --- MICRO-MOVEMENTS (The "Alive" Factor) ---
            # 1-2 degree sway, slow speed.
            # Time-based sine waves with different frequencies for organic feel.
            t = time.time()
            
            # Horizontal sway (Neck): Slow, +/- 1.5 degrees
            sway_h = np.sin(t * 0.8) * 1.5
            
            # Vertical sway (Chin/Head tilt): Very slow, +/- 1.0 degree, slightly offset phase
            sway_v = np.sin(t * 0.5 + 1.2) * 1.0

            # Apply sway to the final servo output (clamped)
            final_neck_angle = self.current_angle + sway_h
            final_z_angle = self.current_eye_v_angle + sway_v

            servo_angle = int(max(self.MIN_ANGLE, min(self.MAX_ANGLE, final_neck_angle)))
            servo_eye_v_angle = int(max(self.EYE_V_MIN, min(self.EYE_V_MAX, final_z_angle)))

            if self.command_callback:
                try:
                    if abs(servo_angle - self.last_sent_angle) >= self.MIN_SERVO_ANGLE_CHANGE:
                        # Priority 2 (Low) for tracking movements
                        self.command_callback(2, f"neck {servo_angle}")
                        self.last_sent_angle = servo_angle

                    if abs(servo_eye_v_angle - self.last_sent_eye_v_angle) >= self.MIN_SERVO_ANGLE_CHANGE:
                        self.command_callback(2, f"z {servo_eye_v_angle}")
                        self.last_sent_eye_v_angle = servo_eye_v_angle
                except Exception as e:
                    print(f"⚠️ Command callback error: {e}")

            # REMOVED: cv2.imshow("Nova Cam Feed (Tracking Enabled)", frame)
            # We do NOT show the feed here to avoid duplicates.
            
            time.sleep(0.001)

        # if self.ser:
        #     self.ser.close()
        #     print("✅ [FaceTracker] Serial port closed.")

    def stop(self):
        if self.running:
            print("Stopping face tracker...")
            self.running = False