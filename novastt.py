#!/usr/bin/env python3
import sounddevice as sd
import numpy as np
import io
import wave
import os
import time
import threading
import collections
from groq import Groq
import config

class SpeechToText:
    """
    Nova STT: Optimized Automatic Voice Activity Detection (VAD) using energy thresholds.
    Eliminates the need for manual keyboard toggles with pre-buffering and adaptive thresholds.
    """

    def __init__(self, on_record_start=None):
        self.client = self._initialize_groq_client()
        self.on_record_start = on_record_start
        self.transcribed_text = None
        self.is_running = True
        
        # Audio Settings - Optimized for low latency
        self.samplerate = config.MIC_SAMPLE_RATE
        self.channels = config.MIC_CHANNELS
        self.threshold = config.STT_ENERGY_THRESHOLD
        self.silence_limit = config.STT_SILENCE_DURATION
        
        # Ultra-optimized Buffers
        self.prebuffer = collections.deque(maxlen=int(self.samplerate * 0.3))  # 300ms prebuffer for faster start
        self.audio_data = []
        self.is_recording = False
        self.silence_start = None
        self.ambient_noise_level = 0
        self.noise_samples = []
        self.max_noise_samples = 30  # Faster ambient noise adaptation

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

    def adaptive_vad_threshold(self, ambient_noise_level):
        """Adaptive VAD threshold based on ambient noise."""
        return max(200, ambient_noise_level * 1.5)

    def _audio_callback(self, indata, frames, time_info, status):
        """Optimized audio callback with pre-buffering and adaptive thresholds."""
        if status:
            print(f"⚠️ Audio Status: {status}")
        
        # Add to prebuffer always
        self.prebuffer.extend(indata.copy().flatten())
        
        # Sample ambient noise during silence
        if not self.is_recording and len(self.noise_samples) < self.max_noise_samples:
            self.noise_samples.append(self._get_energy(indata))
            if len(self.noise_samples) == self.max_noise_samples:
                self.ambient_noise_level = np.mean(self.noise_samples)
                self.threshold = self.adaptive_vad_threshold(self.ambient_noise_level)
                print(f"🎚️ Adaptive threshold set: {self.threshold:.1f}")
            
        energy = self._get_energy(indata)
        adaptive_threshold = self.adaptive_vad_threshold(self.ambient_noise_level) if self.ambient_noise_level > 0 else self.threshold
        
        if energy > adaptive_threshold:
            if not self.is_recording:
                print("🎙️ Voice Detected. Recording...")
                self.is_recording = True
                if self.on_record_start:
                    self.on_record_start()
                
                # Include prebuffered audio
                if self.prebuffer:
                    prebuffer_audio = np.array(list(self.prebuffer)).reshape(-1, self.channels)
                    self.audio_data = [prebuffer_audio]
            
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
        """Optimized transcription using Groq Whisper API."""
        if self.client is None:
            return
            
        try:
            transcription = self.client.audio.transcriptions.create(
                file=("speech.wav", audio_buffer),
                model="whisper-large-v3-turbo",
                response_format="json",
                language="en",
                temperature=0.0
            )
            
            if hasattr(transcription, 'text') and transcription.text:
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
        
        # Start the sounddevice stream with ultra-low latency
        stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            callback=self._audio_callback,
            blocksize=int(self.samplerate * 0.025)  # 25ms chunks for minimal latency
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
