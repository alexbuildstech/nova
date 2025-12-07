# Nova Animatronic Robot

Nova is an advanced, AI-powered animatronic robot based on the InMoov open-source project. It features real-time speech-to-text, LLM-based conversation (Groq/Llama 3), visual perception (Gemini 2.0 Flash), and face tracking with servo control.

## Features

*   **Natural Conversation**: Powered by Llama 3 via Groq for fast, witty, and grounded responses.
*   **Visual Perception**: Uses Google's Gemini 2.0 Flash to "see" and describe the world, rate objects, and answer visual queries.
*   **Face Tracking**: smooth, cinematic face tracking using OpenCV and servo motors (InMoov head).
*   **Voice Interaction**: Real-time speech recognition (Whisper) and text-to-speech.
*   **Web Interface**: A local web dashboard to monitor the robot's status.

## Hardware Requirements

*   **InMoov Robot Head**: (or similar animatronic setup) with servos for neck and eye movements.
*   **Arduino**: For controlling the servos (via serial).
*   **Camera**: USB Webcam or similar.
*   **Microphone**: For voice input.
*   **Speaker**: For audio output.
*   **Computer**: Linux/Windows/Mac to run the Python brain.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/alexbuildstech/nova.git
    cd nova
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    *   Open `config.py`.
    *   **API Keys**: You need a Groq API key and a Google Gemini API key.
        *   Get Groq Key: [https://console.groq.com/](https://console.groq.com/)
        *   Get Gemini Key: [https://aistudio.google.com/](https://aistudio.google.com/)
    *   **Hardware**: Update `CAMERA_INDEX` if your camera isn't detected. Set `SERIAL_PORT` for your Arduino (e.g., `/dev/ttyACM0`).

4.  **Run**:
    ```bash
    python3 novamain.py
    ```

## Usage

*   **Talk**: Press 'c' to start recording your voice. Press 's' to stop and send.
*   **Visual Queries**: Ask "What do you see?", "Look at this", or "Rate this" to trigger the vision system.
*   **Stop**: Press `Ctrl+C` to exit.

## Sponsors

A huge thank you to our sponsors who made this project possible:

*   **Plymaker**: For supporting the 3D printing and fabrication.
*   **DFRobot**: For providing high-quality electronics and components.

## Contributing

We welcome contributions! Please fork the repository and submit a pull request.

## License

This project is open-source and available under the MIT License.
