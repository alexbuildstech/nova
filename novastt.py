#!/usr/bin/env python3
import sounddevice as sd
from pynput import keyboard
import numpy as np
import io
import wave
import os
from groq import Groq
import threading
import config


class SpeechToText:
    """
    STT class with c/s keys: start/stop, transcription stored in a variable.
    """

    GROQ_API_KEY = config.GROQ_API_KEY
    SAMPLERATE = config.MIC_SAMPLE_RATE
    CHANNELS = config.MIC_CHANNELS
    CHUNK = config.MIC_CHUNK_SIZE
    DTYPE = "int16"

    def __init__(self, on_record_start=None):
        self.is_recording = False
        self.stream = None
        self.wave_file = None
        self.audio_buffer = None
        self.listener = None
        self.transcribed_text = None  # <-- store transcription here
        self.client = self._initialize_groq_client()
        self.on_record_start = on_record_start # Callback for when 'c' is pressed

    def _initialize_groq_client(self):
        if not self.GROQ_API_KEY or self.GROQ_API_KEY == "YOUR_GROQ_API_KEY":
            print("Error: GROQ_API_KEY not set")
            return None
        try:
            client = Groq(api_key=self.GROQ_API_KEY)
            client.models.list()
            print("✅ Groq client initialized")
            return client
        except Exception as e:
            print(f"Error initializing Groq client: {e}")
            return None

    def _start_recording(self):
        if self.is_recording:
            print("Already recording")
            return
        self.is_recording = True
        print("▶️ Recording started (press 's' to stop)")
        
        # Trigger callback if registered (e.g., to capture image)
        if self.on_record_start:
            self.on_record_start()
            
        self.audio_buffer = io.BytesIO()
        self.wave_file = wave.open(self.audio_buffer, "wb")
        self.wave_file.setnchannels(self.CHANNELS)
        self.wave_file.setsampwidth(np.dtype(self.DTYPE).itemsize)
        self.wave_file.setframerate(self.SAMPLERATE)

        def audio_callback(indata, frames, time, status):
            if status:
                print(status, flush=True)
            self.wave_file.writeframes(indata.tobytes())

        self.stream = sd.InputStream(
            samplerate=self.SAMPLERATE,
            blocksize=self.CHUNK,
            dtype=self.DTYPE,
            channels=self.CHANNELS,
            callback=audio_callback,
        )
        self.stream.start()

    def _stop_recording_and_transcribe(self):
        if not self.is_recording:
            return
        self.is_recording = False
        print("⏹️ Recording stopped")
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if self.wave_file:
            self.wave_file.close()
        print("Transcribing...")
        
        # Get the data from the buffer
        self.audio_buffer.seek(0)
        audio_data = self.audio_buffer.read()

        # Run transcription in a thread so listener keeps working
        threading.Thread(
            target=self._transcribe_audio, args=(audio_data,), daemon=True
        ).start()

    def _transcribe_audio(self, audio_data):
        try:
            transcription = self.client.audio.transcriptions.create(
                file=("audio.wav", audio_data),
                model="whisper-large-v3-turbo",
                language="en",
            )
            text = transcription.text.strip()

            # ADD: replace "Noah" with "Nova"
            text = text.replace("Noah", "Nova")

            print(f"📝 Transcription: {text}")
            self.transcribed_text = text  # <-- store here for main code
        except Exception as e:
            print(f"Transcription error: {e}")
            self.transcribed_text = None


    def _on_key_press(self, key):
        try:
            if key.char == "c":
                self._start_recording()
            elif key.char == "s":
                self._stop_recording_and_transcribe()
        except AttributeError:
            pass

    def _terminal_input_loop(self):
        print("⌨️ Terminal Input Active: Type a command and press Enter. Type 'exit' to quit.")
        while True:
            try:
                text = input()
                if text.strip():
                    if text.strip().lower() == "exit":
                        self.transcribed_text = "#EXIT"
                    else:
                        self.transcribed_text = text.strip()
            except EOFError:
                break
            except Exception as e:
                print(f"Terminal input error: {e}")

    def start_listener(self):
        if not self.client:
            print("Groq client not initialized")
            return
        print("\n--- STT ready --- Press 'c' to record, 's' to stop ---\n")
        
        # Start keyboard listener
        self.listener = keyboard.Listener(on_press=self._on_key_press)
        self.listener.start()
        
        # Start terminal input thread
        threading.Thread(target=self._terminal_input_loop, daemon=True).start()

