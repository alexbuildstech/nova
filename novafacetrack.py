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
                return cap
            else:
                print(f"⚠️ [FaceTracker] Camera index {try_idx} unavailable, trying next.")
        return None

    def _camera_reader_loop(self):
        # Try to open the configured camera index, fallback to next indices if unavailable
        cap = self._open_camera(self.CAMERA_INDEX)
        if not cap:
            print("❌ [FaceTracker] No available camera found. Running in AUDIO-ONLY mode.")
            self.running = False
            return
            
        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            
            if self.camera_output_queue.full():
                try: self.camera_output_queue.get_nowait()
                except queue.Empty: pass
            self.camera_output_queue.put(frame)
        
        cap.release()
        print("✅ Camera reader thread stopped.")

    def _face_detection_loop(self):
        while self.running:
            try:
                frame_copy = self.detection_frame_queue.get(timeout=1)
            except queue.Empty:
                continue

            (h, w) = frame_copy.shape[:2]
            
            h_dead_zone_start = w * (0.5 - self.HORIZONTAL_DEAD_ZONE_PERCENT / 2)
            h_dead_zone_end = w * (0.5 + self.HORIZONTAL_DEAD_ZONE_PERCENT / 2)
            
            blob = cv2.dnn.blobFromImage(cv2.resize(frame_copy, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
            self.net.setInput(blob)
            detections = self.net.forward()

            best_confidence = 0
            best_face_box = None
            found_face_this_frame = False

            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > self.CONFIDENCE_THRESHOLD and confidence > best_confidence:
                    found_face_this_frame = True
                    best_confidence = confidence
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    best_face_box = box.astype("int")
                    
                    face_center_x = (best_face_box[0] + best_face_box[2]) / 2

                    if not (h_dead_zone_start < face_center_x < h_dead_zone_end):
                        # FIX: This mapping is now correct. Right on screen = right turn.
                        self.target_angle = self._map_value(face_center_x, 0, w, self.MIN_ANGLE, self.MAX_ANGLE)
            
            if found_face_this_frame:
                box_width = best_face_box[2] - best_face_box[0]
                
                # Dynamic speed logic based on face distance
                self.dynamic_max_angle_step = self._map_value(box_width, self.MIN_FACE_WIDTH_SCALE, self.MAX_FACE_WIDTH_SCALE, self.MAX_STEP_FAR, self.MIN_STEP_CLOSE)
                self.dynamic_max_angle_step = max(self.MIN_STEP_CLOSE, min(self.dynamic_max_angle_step, self.MAX_STEP_FAR))

                # RESTORED: Direct, responsive z-axis mapping for cinematic feel
                self.target_eye_v_angle = self._map_value(box_width, self.MIN_FACE_WIDTH_SCALE, self.MAX_FACE_WIDTH_SCALE, self.EYE_V_MAX, self.EYE_V_MIN)

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