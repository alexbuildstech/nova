# novafacetracker.py

import cv2
import time
import threading
import numpy as np
import queue
import config

class FaceTracker(threading.Thread):
    def __init__(self, command_callback=None, camera_index=1):
        super().__init__()
        self.daemon = True
        self.command_callback = command_callback
        self.running = False

        # --- Constants & Configuration ---
        self.CAMERA_INDEX = camera_index
        self.MIN_ANGLE = config.SERVO_MIN_ANGLE
        self.MAX_ANGLE = config.SERVO_MAX_ANGLE
        self.MIN_SERVO_ANGLE_CHANGE = 3
        self.CONFIDENCE_THRESHOLD = config.CONFIDENCE_THRESHOLD
        self.DETECTION_INTERVAL = 0.033  # 30 FPS
        
        # Enhanced motion detection optimization
        self.MOTION_THRESHOLD = 0.08
        self.FRAME_SKIP_COUNT = 0
        self.FRAME_SKIP_THRESHOLD = 5
        self.prev_frame = None
        self.motion_detected = False
        self.last_detection_time = 0
        self.detection_cooldown = 0.1

        # --- Vertical Eye Movement Config ---
        self.EYE_V_MIN = config.EYE_V_MIN
        self.EYE_V_MID = config.EYE_V_MID
        self.EYE_V_MAX = config.EYE_V_MAX

        # --- Frame sharing and threading ---
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.last_known_face_box = None
        self.box_lock = threading.Lock()
        
        # --- Queues for Inter-thread Communication ---
        self.detection_frame_queue = queue.Queue(maxsize=1)
        self.camera_output_queue = queue.Queue(maxsize=1)

        print("ℹ️ Loading DNN Face Detector model...")
        self.net = cv2.dnn.readNetFromCaffe(
            config.PROTOTXT_PATH, config.CAFFEMODEL_PATH
        )
        print("✅ DNN Model Loaded.")

        # --- State Variables ---
        self.NEUTRAL_ANGLE = 80
        self.current_x_angle = self.NEUTRAL_ANGLE
        self.current_y_angle = self.NEUTRAL_ANGLE
        self.target_angle = self.NEUTRAL_ANGLE
        self.current_angle = self.NEUTRAL_ANGLE
        self.last_sent_angle = -999
        self.target_eye_v_angle = self.EYE_V_MID
        self.current_eye_v_angle = self.EYE_V_MID
        self.last_sent_eye_v_angle = -999
        self.dynamic_max_angle_step = 8.0

    def get_latest_frame(self):
        """Thread-safe frame access."""
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
        return None

    def detect_motion(self, frame1, frame2):
        """Optimized motion detection using frame difference."""
        if frame1 is None or frame2 is None:
            return True
            
        diff = cv2.absdiff(cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY), 
                          cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY))
        motion_score = np.mean(diff) / 255.0
        return motion_score > self.MOTION_THRESHOLD

    def _camera_reader_loop(self):
        """Independent camera reader thread."""
        cap = cv2.VideoCapture(self.CAMERA_INDEX)
        if not cap.isOpened():
            print(f"❌ Error: Could not open camera {self.CAMERA_INDEX}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue
            
            if not self.camera_output_queue.full():
                self.camera_output_queue.put(frame)
        
        cap.release()

    def _face_detection_loop(self):
        """Independent face detection thread."""
        while self.running:
            try:
                frame = self.detection_frame_queue.get(timeout=1)
            except queue.Empty:
                continue

            current_time = time.time()
            if self.prev_frame is not None and (current_time - self.last_detection_time) > self.detection_cooldown:
                if not self.detect_motion(self.prev_frame, frame):
                    self.FRAME_SKIP_COUNT += 1
                    if self.FRAME_SKIP_COUNT < self.FRAME_SKIP_THRESHOLD:
                        continue
                    else:
                        self.FRAME_SKIP_COUNT = 0
                else:
                    self.FRAME_SKIP_COUNT = 0
                    self.last_detection_time = current_time
            
            self.prev_frame = frame.copy()

            (h, w) = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                (300, 300), (104.0, 177.0, 123.0))

            self.net.setInput(blob)
            detections = self.net.forward()

            best_face_box = None
            max_confidence = 0

            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > self.CONFIDENCE_THRESHOLD:
                    if confidence > max_confidence:
                        max_confidence = confidence
                        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                        best_face_box = box.astype("int")

            if best_face_box is not None:
                with self.box_lock:
                    self.last_known_face_box = best_face_box
                
                (startX, startY, endX, endY) = best_face_box
                face_center_x = (startX + endX) // 2
                face_center_y = (startY + endY) // 2
                
                # Update targets based on face position
                error_x = face_center_x - (w // 2)
                error_y = face_center_y - (h // 2)
                
                if abs(error_x) > 20:
                    self.target_angle -= error_x * 0.05
                if abs(error_y) > 20:
                    self.target_eye_v_angle = np.interp(face_center_y, [0, h], [self.EYE_V_MAX, self.EYE_V_MIN])

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
                continue

            with self.frame_lock:
                self.latest_frame = frame
            
            if not self.detection_frame_queue.full():
                self.detection_frame_queue.put(frame.copy())

            # --- Servo Smoothing Logic ---
            delta_angle = self.target_angle - self.current_angle
            step = max(-self.dynamic_max_angle_step, min(self.dynamic_max_angle_step, delta_angle))
            if abs(delta_angle) > 1: self.current_angle += step
            
            delta_eye_v = self.target_eye_v_angle - self.current_eye_v_angle
            step_eye_v = max(-self.dynamic_max_angle_step, min(self.dynamic_max_angle_step, delta_eye_v))
            if abs(delta_eye_v) > 1: self.current_eye_v_angle += step_eye_v

            # --- MICRO-MOVEMENTS (The "Alive" Factor) ---
            t = time.time()
            sway_h = np.sin(t * 0.8) * 1.5
            sway_v = np.sin(t * 0.5 + 1.2) * 1.0

            final_neck_angle = self.current_angle + sway_h
            final_z_angle = self.current_eye_v_angle + sway_v

            servo_angle = int(max(self.MIN_ANGLE, min(self.MAX_ANGLE, final_neck_angle)))
            servo_eye_v_angle = int(max(self.EYE_V_MIN, min(self.EYE_V_MAX, final_z_angle)))

            if self.command_callback:
                try:
                    if abs(servo_angle - self.last_sent_angle) >= self.MIN_SERVO_ANGLE_CHANGE:
                        self.command_callback(2, f"neck {servo_angle}")
                        self.last_sent_angle = servo_angle

                    if abs(servo_eye_v_angle - self.last_sent_eye_v_angle) >= self.MIN_SERVO_ANGLE_CHANGE:
                        self.command_callback(2, f"z {servo_eye_v_angle}")
                        self.last_sent_eye_v_angle = servo_eye_v_angle
                except Exception as e:
                    print(f"⚠️ Command callback error: {e}")

            time.sleep(0.001)

    def stop(self):
        print("Stopping face tracker...")
        self.running = False
