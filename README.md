# Nova - Open Source AI Robot Software for InMoov

![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-lightgrey.svg)

**Nova** is a state-of-the-art, independent software stack designed specifically for the **InMoov** open-source 3D printed robot platform. It transforms static animatronics into fully autonomous, conversational humanoid robots using advanced **Artificial Intelligence**.

Unlike traditional script-based robotics, Nova leverages **Large Language Models (LLMs)** like **OpenAI GPT-OSS-20B** and **Computer Vision** models like **Google Gemini 2.0 Flash Vision** to enable real-time, dynamic interaction. Whether you are running on a high-end PC, an **NVIDIA Jetson**, or a powerful SBC like the **Radxa rock 5C**, Nova provides the intelligence your robot needs.

> **Note:** This project is currently an independent fork and is **not yet integrated with MyRobotLab**, though future compatibility is on our roadmap.

---

## 📑 Table of Contents
- [Key Features](#-key-features)
- [Hardware Requirements](#-hardware-requirements)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Sponsors](#-sponsors)
- [Roadmap](#-roadmap)
- [License](#-license)

---

## 🚀 Key Features

*   **🧠 Advanced LLM Integration**: Powered by **OpenAI GPT-OSS-20B** (via Groq) for ultra-low latency, human-like conversation.
*   **👁️ Computer Vision & Perception**: Uses **Google Gemini 2.0 Flash Vision** to analyze the visual world, describe objects, and read text in real-time.
*   **🌐 Real-Time Internet Access**: Integrated **Google Search** allows Nova to answer questions about current events, weather, and news.
*   **🤖 Autonomous Face Tracking**: PID-controlled servo tracking ensures Nova maintains eye contact, creating a "living" presence.
*   **🗣️ Natural Voice Interaction**: Features high-fidelity **Speech-to-Text (STT)** and **Text-to-Speech (TTS)** for seamless verbal communication.
*   **💻 Web Control Dashboard**: A local web interface for easy monitoring, debugging, and control.

---

## 🛠️ Hardware Requirements

Nova is optimized for the **InMoov** robot head but is compatible with various animatronic setups.

*   **Compute**:
    *   **Recommended**: Linux/Windows PC with NVIDIA GPU.
    *   **SBCs**: Compatible with **Radxa rock 5C**, **Raspberry Pi 5**, or **NVIDIA Jetson Orin Nano**.
*   **Microcontroller**: Arduino Uno or Mega (for servo control via Serial).
*   **Vision**: USB Webcam (Logitech C920 recommended).
*   **Audio**: USB Microphone & Speakers.
*   **Mechanics**: Standard Hobby Servos (MG996R/SG90) for InMoov neck and eye mechanisms.

---

## 📦 Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/alexbuildstech/nova.git
    cd nova
    ```

2.  **Install Python Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **System Setup**
    Ensure you have `ffmpeg` installed for audio processing:
    ```bash
    sudo apt install ffmpeg  # Linux
    # or download for Windows
    ```

---

## ⚙️ Configuration

Nova uses a central configuration file for security and ease of use.

1.  Open `config.py`.
2.  **API Keys**: Enter your **Groq API Key** and **Google Gemini API Key**.
3.  **Hardware**: Set your `CAMERA_INDEX` and `SERIAL_PORT`.

```python
# config.py example
GROQ_API_KEY = "your_key_here"
CAMERA_INDEX = 0  # 0 for default webcam
SERIAL_PORT = "/dev/ttyACM0"  # or 'COM3' on Windows
```

---

## 🤝 Sponsors

We are proud to be supported by industry leaders in making and robotics:

### **Polymaker**
Leading the way in advanced 3D printing materials. **Polymaker** provides the high-quality PLA and specialized filaments that bring Nova's physical form to life.

### **DFRobot**
A world-leading robotics and open-source hardware provider. **DFRobot** supplies the essential sensors, microcontrollers, and electronic components that power Nova's intelligence.

### **Radxa**
Innovators in Single Board Computers (SBCs). **Radxa** provides the powerful computing SBC (like rock 5c) that drive Nova's AI processing capabilities.

---

## 🔮 Roadmap

*   **MyRobotLab Integration**: Full plugin support for the MyRobotLab ecosystem.
*   **Gesture Control**: Hand tracking and arm movement synchronization for InMoov arms.
*   **Local LLM Support**: Offline inference using **Llama 3** via Ollama.
*   **Emotion Engine**: Dynamic facial expression mapping based on sentiment analysis.

---

## 📄 License

This project is open-source and available under the **MIT License**.

---

*Keywords: InMoov, AI Robot, Python, LLM, Computer Vision, OpenAI, Gemini, Robotics, Animatronics, Open Source, Artificial Intelligence, Face Tracking, Voice Assistant, Radxa, Polymaker, DFRobot, MyRobotLab, Raspberry Pi, NVIDIA Jetson.*
