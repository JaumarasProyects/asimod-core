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

---

## 🎮 Connecting Unity / Unreal / APK

To connect your project:
1. **Run the Core:** Launch `run_headless.bat` (API only) or `run_chat.bat` (GUI + API).
2. **HTTP Client:** Use `UnityWebRequest` (C#) or `HTTP Request` (Blueprints/C++) to point to `http://YOUR_PC_IP:8000/v1/chat`.
3. **Handle Response:** Parse the JSON to get the text response and the list of emojis for your character's facial expressions.

---

## 🖥️ Execution Modes

- **Desktop (GUI):** `python main_standalone.py` - Full chat interface with Vision controls.
- **Server (Headless):** `python main_headless.py` - Lightweight API-only mode for background usage.

---

## 🔒 License & Security
- **Privacy:** `settings.json` and `output/vision/` are automatically ignored by Git. 
- **License:** Private use.

Developed with ❤️ for the ASIMOD Ecosystem.
