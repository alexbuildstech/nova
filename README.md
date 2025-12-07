# Nova AI Robot - Advanced Open Source InMoov Modification

**Nova** is a cutting-edge, independent software modification for the **InMoov** open-source 3D printed robot. Designed to bring static animatronics to life, Nova integrates advanced **Large Language Models (LLMs)**, **Computer Vision**, and **Real-Time Voice Interaction** to create a fully autonomous, conversational humanoid robot.

> **Note:** This project is independent software and is currently **not connected to MyRobotLab**, although future integration is planned.

---

## 🚀 Key Features

*   **Advanced Conversational AI**: Powered by **OpenAI GPT-OSS-20B** (via Groq) for ultra-fast, human-like dialogue.
*   **Visual Perception**: Utilizes **Google Gemini 2.0 Flash Vision** to see, analyze, and describe the world in real-time.
*   **Real-Time Information**: Integrated **Google Search** capabilities for up-to-the-minute news, weather, and data.
*   **Face Tracking & Eye Contact**: Autonomous servo control for realistic face tracking and "Absolute Cinema" eye movement dynamics.
*   **Voice Interaction**: Low-latency Speech-to-Text (STT) and Text-to-Speech (TTS) for seamless verbal communication.
*   **Web Dashboard**: A local web interface for monitoring and control.

---

## 🛠️ Hardware Requirements

Nova is optimized for the **InMoov** robot platform but can be adapted for other animatronic heads.

*   **Computer**: Linux/Windows PC (NVIDIA GPU recommended for local inference, but cloud APIs are supported).
*   **Microcontroller**: Arduino Uno/Mega (for servo control).
*   **Camera**: USB Webcam (Logitech C920 or similar).
*   **Microphone**: High-quality USB microphone.
*   **Servos**: Standard hobby servos for neck and eye mechanisms.

---

## 📦 Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/alexbuildstech/nova.git
    cd nova
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**
    *   Open `config.py`.
    *   Add your API Keys (**Groq**, **Google Gemini**).
    *   Configure your hardware settings (Camera Index, Serial Port).

4.  **Run Nova**
    ```bash
    python3 novamain.py
    ```

---

## 🤝 Sponsors

This project is made possible by the generous support of our sponsors:

### **Polymaker**
Leading the way in advanced 3D printing materials. Polymaker provides the high-quality filament that brings Nova's physical form to life.

### **DFRobot**
A world-leading robotics and open-source hardware provider. DFRobot supplies the essential electronics and sensors that power Nova's intelligence.

### **Radxa**
Innovators in Single Board Computers (SBCs). Radxa provides the powerful computing core that drives Nova's AI processing.

---

## 🔮 Future Roadmap

*   **MyRobotLab Integration**: Full compatibility with the MyRobotLab ecosystem.
*   **Gesture Control**: Hand tracking and arm movement synchronization.
*   **Local LLM Support**: Offline inference using Llama 3.

---

## 📄 License

This project is open-source and available under the MIT License.

---

*Keywords: InMoov, AI Robot, Python, LLM, Computer Vision, OpenAI, Gemini, Robotics, Animatronics, Open Source, Artificial Intelligence, Face Tracking, Voice Assistant.*
