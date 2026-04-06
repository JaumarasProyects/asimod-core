# ASIMOD Core 🤖🌌

**ASIMOD Core** (Advanced Sensory Integrated Multimodal Orchestrating Device) is a powerful, lightweight, and modular AI orchestrator designed to serve as the "brain" for digital avatars, robots, and interactive applications.

Built with a **Ports & Adapters Architecture**, it allows seamless integration with multiple LLM providers, Vision systems, and Voice engines, exposing everything through a high-performance REST API.

---

## 🚀 Key Features

- **Multimodal Vision:** Capable of "seeing" through webcams, screen captures, and local files.
- **Emotional Intelligence:** Automatic emoji extraction and text cleaning for realistic avatar animations.
- **High Performance:** Fully asynchronous and non-blocking architecture (Multi-threading).
- **Universal API:** Ready to connect with **Unity, Unreal Engine, Android (APK), or Web Frontends**.
- **Provider Agnostic:** Supports OpenAI, Gemini, Ollama, Groq, Perplexity, and more.

---

## 🎤 Voice Playback Modes

ASIMOD Core supports two voice playback modes:
- **Interrupt Mode:** Immediately stops any playing audio and starts new playback.
- **Wait Mode:** Queues new audio requests and plays them sequentially.

Configure via `settings.json` or use the desktop UI:
```json
{
  "voice_playback_mode": "interrupt"
}
```

### Visualizer System
A modular waveform visualizer can display audio playback:
- **Port/Adapter Architecture:** `core/ports/visualizer_port.py` defines the interface
- **Adapters:** `core/adapters/waveform_visualizer.py` provides waveform display
- Enable via `settings.json`: `"visualizer_enabled": true`

---

## 🛠️ Configuration

The system uses a `settings.json` file for persistence. 

> [!IMPORTANT]
> The `settings.json` file is ignored by Git to protect your API Keys. You must create or edit it manually in the root folder.

### Adding API Keys
Open `settings.json` and fill in your credentials for the providers you wish to use:
```json
{
  "openai_key": "your-key-here",
  "gemini_key": "your-key-here",
  "groq_key": "your-key-here",
  "ollama_url": "http://localhost:11434"
}
```

---

## 🔌 API Documentation

ASIMOD Core exposes a REST API (FastAPI) on port `8000` (configurable), allowing external applications to control the brain and receive processed data.

### 1. Conversation Engine
**`POST /v1/chat`**
Send a message to the AI.
- **Payload:**
  ```json
  {
    "text": "Hello, how are you?",
    "model": "gpt-4o" 
  }
  ```
- **Response:**
  ```json
  {
    "response": "Hello! I'm feeling great today! 😊",
    "clean_text": "Hello! I'm feeling great today!",
    "emojis": ["😊"],
    "status": "success"
  }
  ```
  *Use `clean_text` for your TTS engine and `emojis` to trigger avatar animations.*

### 2. Remote Configuration
**`POST /v1/config`**
Dynamically switch providers, models, or voices.
- **Payload:** `{"last_provider": "Ollama", "voice_id": "8"}`

### 3. System Status
**`GET /v1/status`**
Returns current configuration, active providers, and audio save paths.

### 4. Utilities
- **`GET /v1/providers`**: List all available LLM engines.
- **`GET /v1/models`**: List models for the current provider.
- **`GET /v1/voices`**: List available TTS voices.
- **`POST /v1/audio/stop`**: Stop current PC audio playback.
- **`POST /v1/audio/pause/resume`**: Control local microphone capture.
- **`GET /v1/audio/status`**: Get current playback status.
- **`GET /v1/audio/playback_mode`**: Get current playback mode (interrupt/wait).
- **`POST /v1/audio/playback_mode`**: Set playback mode.

---

---

## 🔌 Official Adapters

We provide ready-to-use integration scripts for the most popular engines and languages.

### 🎮 Unity Engine (C#)
- **Folder:** `UnityIntegration/`
- **File:** `AsimodClient.cs`
- **Usage:** Attach the `AsimodClient` MonoBehaviour to any GameObject. 
- **Features:** Asynchronous `UnityWebRequest` with callbacks for `clean_text` and `emojis`.

### 🎮 Unreal Engine (C++)
- **Folder:** `UnrealIntegration/`
- **Files:** `AsimodClient.cpp/h`
- **Usage:** Add the `UAsimodClient` Actor Component to your character or controller.
- **Features:** Fully exposed to **Blueprints** via Delegates (`OnChatReceived`).

### 🐍 Python Client
- **Folder:** `PythonIntegration/`
- **File:** `asimod_client.py`
- **Usage:** `from asimod_client import AsimodClient`.
- **Features:** Simple synchronous wrapper using the `requests` library.

### 🎮 Godot Engine (GDScript)
- **Folder:** `GodotIntegration/`
- **File:** `AsimodClient.gd`
- **Usage:** Add to your **Autoloads (Singleton)** or attach to a Node.
- **Features:** Uses `HTTPRequest` and signals (`chat_received`) for non-blocking logic.

---

## 🖥️ Execution Modes

- **Desktop (GUI):** `python main_standalone.py` - Full chat interface with Vision controls.
- **Server (Headless):** `python main_headless.py` - Lightweight API-only mode for background usage.

---

## 🔒 License & Security
- **Privacy:** `settings.json` and `output/vision/` are automatically ignored by Git. 
- **License:** Private use.

Developed with ❤️ for the ASIMOD Ecosystem.
