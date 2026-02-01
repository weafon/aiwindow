# AI Window Assistant (Gemini Live Edition)

AI Window is a minimalist, transparent window assistant that combines real-time voice interaction with immersive background scenes. Powered by Gemini Live and YouTube, it allows you to transform your workspace with just a voice command.

## 🌟 Features

- **Real-time Voice Interaction**: Bidirectional streaming using `gemini-2.5-flash-native-audio-preview`.
- **Smart Scene Switching**: Automatically searches and plays YouTube 4K window views (e.g., "Rainy London", "Swiss Alps") based on conversation keywords.
- **Intelligent Audio Management**:
  - **Auto-Pause**: Background music/video automatically pauses when you start talking to the AI.
  - **Auto-Resume**: Background audio resumes seamlessly once the conversation ends.
  - **Jitter Buffer**: Advanced latency management to prevent audio stuttering during network bursts.
- **Minimalist UI**: A sleek, transparent, and "always-on-top" PyQt6 interface.
- **Auto Mic Closure**: The assistant automatically closes the microphone 6 seconds after a search command is detected, allowing it to finish its verbal confirmation.

## 🛠️ Prerequisites

- **Python 3.10+**
- **FFmpeg**: Required for audio processing.
- **MPV**: Required for background video playback.
- **yt-dlp**: Required for searching YouTube content.
- **Dependencies**:
  ```bash
  pip install PyQt6 google-genai nest_asyncio
  ```

## 🚀 Setup

1. **Get a Gemini API Key**: Visit the [Google AI Studio](https://aistudio.google.com/) to get your key.
2. **Set Environment Variable**:
   ```bash
   export GEMINI_API_KEY='your_api_key_here'
   ```
3. **Start MPV with IPC**:
   Open a terminal and start MPV with the IPC socket enabled (required for auto-pause):
   ```bash
   mpv --idle --input-ipc-server=/tmp/mpvsocket --background=no --geometry=100%x100%
   ```
4. **Run AI Window**:
   ```bash
   python3 ai_window.py
   ```

## 🎙️ Usage

- **Voice Command**: Click the 🎤 button to start a Live session.
- **Switch Scenes**: Tell the AI something like:
  - *"I want to see the rainy streets of London."*
  - *"Show me a snowy mountain view."*
  - *"帮我换成日本街道的风景"* (Support for Traditional Chinese).
- **Text Entry**: You can also type commands into the input field at the bottom.
- **Exit**: Click the '✕' or press `Esc`.

## ⚙️ Technical Details

- **Audio Configuration**:
  - Recording: 16kHz, 16-bit PCM.
  - Playback: 24kHz, 16-bit PCM (standard for Gemini Live output).
- **Jitter Buffer**: Built with a 5-second burst tolerance and 20ms check intervals to ensure smooth playback regardless of network conditions.
- **Device Selection**: Automatically prioritizes external microphones (USB Audio, ConferenceCam) for better voice quality.

## 📝 License

This project is for demonstration and personal use. Powered by Google Gemini.
