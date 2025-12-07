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
            
        print("\n🎙️ Audio Capture Active...")
        frames = []
        
        # Open audio stream
        with self.microphone as source:
            # Dynamic ambient noise adjustment
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            while self.is_recording:
                try:
                    audio_chunk = source.stream.read(config.MIC_CHUNK_SIZE)
                    frames.append(audio_chunk)
                except Exception as e:
                    print(f"⚠️ Audio Stream Error: {e}")
                    break
        
        print("⏹️ Audio Capture Complete. Processing...")
        
        # Convert raw PCM data to AudioData object
        audio_data = sr.AudioData(b''.join(frames), source.SAMPLE_RATE, source.SAMPLE_WIDTH)
        return audio_data

    def transcribe_audio(self, audio_data):
        """
        Transcribes captured audio using the Groq Whisper API.
        Delivers near-instantaneous text conversion for fluid conversation.
        """
        try:
            # Save temporary buffer for API transmission
            temp_filename = "temp_speech.mp3"
            with open(temp_filename, "wb") as f:
                f.write(audio_data.get_wav_data())
            
            with open(temp_filename, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(temp_filename, file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="json",
                    language="en",
                    temperature=0.0
                )
            
            text = transcription.text.strip()
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

