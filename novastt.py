#!/usr/bin/env python3
import sounddevice as sd
import numpy as np
import io
import wave
import os
import time
import threading
from groq import Groq
import config

class SpeechToText:
    """
    Nova STT: Automatic Voice Activity Detection (VAD) using energy thresholds.
    Eliminates the need for manual keyboard toggles.
    """

    def __init__(self, on_record_start=None):
        self.client = self._initialize_groq_client()
        self.on_record_start = on_record_start
        self.transcribed_text = None
        self.is_running = True
        
        # Audio Settings
        self.samplerate = config.MIC_SAMPLE_RATE
        self.channels = config.MIC_CHANNELS
        self.threshold = config.STT_ENERGY_THRESHOLD
        self.silence_limit = config.STT_SILENCE_DURATION
        
        # Buffers
        self.audio_data = []
        self.is_recording = False
        self.silence_start = None

    def _initialize_groq_client(self):
        try:
            client = Groq(api_key=config.GROQ_API_KEY)
            return client
        except Exception as e:
            print(f"❌ Groq Init Error: {e}")
            return None

    def _get_energy(self, audio_chunk):
        """Calculates the RMS energy of an audio chunk."""
        return np.sqrt(np.mean(audio_chunk**2))

    def _audio_callback(self, indata, frames, time_info, status):
        """Processes incoming audio chunks for VAD."""
        if status:
            print(f"⚠️ Audio Status: {status}")
            
        energy = self._get_energy(indata)
        
        if energy > self.threshold:
            if not self.is_recording:
                print("🎙️ Voice Detected. Recording...")
                self.is_recording = True
                if self.on_record_start:
                    self.on_record_start()
            
            self.audio_data.append(indata.copy())
            self.silence_start = None
        elif self.is_recording:
            # Continue recording brief silence to avoid clipping
            self.audio_data.append(indata.copy())
            
            if self.silence_start is None:
                self.silence_start = time.time()
            elif time.time() - self.silence_start > self.silence_limit:
                print("⏹️ Silence Detected. Processing...")
                self.is_recording = False
                self._process_recording()

    def _process_recording(self):
        """Converts buffer to WAV and sends to Groq."""
        if not self.audio_data:
            return

        recording = np.concatenate(self.audio_data)
        self.audio_data = [] # Reset buffer
        
        # Convert to 16-bit PCM
        recording_int = (recording * 32767).astype(np.int16)
        
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(self.samplerate)
            wf.writeframes(recording_int.tobytes())
        
        buffer.seek(0)
        threading.Thread(target=self._transcribe, args=(buffer,), daemon=True).start()

    def _transcribe(self, audio_buffer):
        """Transcribes audio using Groq Whisper API."""
        try:
            transcription = self.client.audio.transcriptions.create(
                file=("speech.wav", audio_buffer),
                model="whisper-large-v3-turbo",
                response_format="json",
                language="en",
                temperature=0.0
            )
            
            text = transcription.text.strip()
            if text:
                print(f"📝 Transcribed: \"{text}\"")
                self.transcribed_text = text
        except Exception as e:
            print(f"❌ Transcription Error: {e}")

    def start_listener(self):
        """Starts the non-blocking background audio monitor."""
        if not self.client:
            return

        print(f"✅ STT Listener Active (Threshold: {self.threshold})")
        
        # Start the sounddevice stream
        stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            callback=self._audio_callback,
            blocksize=int(self.samplerate * 0.1) # 100ms chunks
        )
        stream.start()
        
        # Keep the thread alive if needed, or rely on main thread
        # In Nova, novamain.py keeps the process alive.

if __name__ == "__main__":
    # Test block
    stt = SpeechToText()
    stt.start_listener()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
