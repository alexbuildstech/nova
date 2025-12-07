import threading
from flask import Flask, render_template, Response, jsonify, request
import cv2
import time

class WebInterface(threading.Thread):
    def __init__(self, stt_service, robot, face_tracker, host='0.0.0.0', port=5000):
        super().__init__()
        self.stt_service = stt_service
        self.robot = robot
        self.face_tracker = face_tracker
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.daemon = True  # Daemon thread exits when main program exits

        # Define routes
        self.app.add_url_rule('/', 'index', self.index)
        self.app.add_url_rule('/video_feed', 'video_feed', self.video_feed)
        self.app.add_url_rule('/command/record_start', 'record_start', self.record_start, methods=['POST'])
        self.app.add_url_rule('/command/record_stop', 'record_stop', self.record_stop, methods=['POST'])
        self.app.add_url_rule('/command/speech_stop', 'speech_stop', self.speech_stop, methods=['POST'])
        self.app.add_url_rule('/command/reset', 'reset', self.reset, methods=['POST'])
        self.app.add_url_rule('/status', 'status', self.get_status)

    def run(self):
        print(f"🚀 Starting Web Interface on http://{self.host}:{self.port}")
        # Disable reloader to avoid running in a separate process which breaks shared state
        self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)

    def index(self):
        return render_template('index.html')

    def gen_frames(self):
        while True:
            frame = self.face_tracker.get_latest_frame()
            if frame is not None:
                # Encode frame as JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                # If no frame, yield a placeholder or wait
                time.sleep(0.1)

    def video_feed(self):
        return Response(self.gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

    def record_start(self):
        print("🌐 Web Command: Start Recording")
        if not self.stt_service.is_recording:
            self.stt_service._start_recording()
            return jsonify({"status": "recording_started"})
        return jsonify({"status": "already_recording"})

    def record_stop(self):
        print("🌐 Web Command: Stop Recording")
        if self.stt_service.is_recording:
            self.stt_service._stop_recording_and_transcribe()
            return jsonify({"status": "recording_stopped"})
        return jsonify({"status": "not_recording"})

    def speech_stop(self):
        print("🌐 Web Command: Terminate Speech")
        self.robot.stop_speech()
        return jsonify({"status": "speech_terminated"})

    def reset(self):
        print("🌐 Web Command: Reset")
        # Implement reset logic if needed, e.g., clearing chat history in memory
        # For now, we'll just return success
        return jsonify({"status": "reset_ok"})

    def get_status(self):
        status = {
            "is_recording": self.stt_service.is_recording,
            "camera_active": self.face_tracker.running
        }
        return jsonify(status)
