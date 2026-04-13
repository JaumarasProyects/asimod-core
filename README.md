# ASIMOD Core: Universal Agentic Orchestrator 🤖🌌

**ASIMOD Core** (Advanced Sensory Integrated Multimodal Orchestrating Device) is a comprehensive framework for building autonomous, multimodal agents. It acts as a universal "brain" that can be specialized through modular plugins, connecting high-level reasoning with real-world sensors and communication channels.

---

## 🏗️ System Architecture: Ports & Adapters

ASIMOD is built on a Hexagonal Architecture (Ports & Adapters), ensuring that the core reasoning logic is completely decoupled from sensory implementations and external frontends.

```mermaid
graph TD
    User([User]) <--> Gateways[Gateways: Web, WhatsApp, Telegram, Standalone]
    Gateways <--> Core[ASIMOD Core Orchestrator]
    
    subgraph Reasoning ["The AI Brain"]
        Core <--> Engine[Agentic Reasoning Engine]
        Engine <--> LLM[Adapters: OpenAI, Gemini, Ollama, GGUF]
    end
    
    subgraph Sensory ["Sensory Perception"]
        Core <--> Vision[Vision: Cam, Screen, OCR]
        Core <--> Audio[Audio: STT, TTS, Destreaming]
    end
    
    subgraph Ecosystem ["Modular Utility"]
        Core <--> Modules[[Independent Modules: Media, Health, Projects]]
    end
```

---

## 🔌 The Integration Ecosystem

ASIMOD supports a wide array of providers right out of the box, allowing you to mix and match local and cloud-based services.

### 🧠 Language Models (LLM)
- **Cloud:** OpenAI (GPT-4o), Google Gemini, Anthropic Claude.
- **Local:** Ollama, GGUF (Direct load via llama.cpp), LLM Studio, OpenCode.

### 👂 Sensory Inputs (STT & Vision)
- **Speech-to-Text:** Whisper (OpenAI), Faster-Whisper (Local), Google Cloud STT.
- **Computer Vision:** Real-time Camera capture, Screen analysis, and local file processing.

### 🗣️ Voice Output (TTS)
- **Edge TTS:** High-fidelity, multilingual neural voices.
- **Local TTS:** Offline synthesis options.
- **Destreaming Logic:** Intelligent chunking of LLM responses for low-latency audio playback.

---

## 🌐 Connectivity & Gateways

ASIMOD isn't restricted to a single window. It can be accessed through multiple channels simultaneously:

- **Web Dashboard:** A professional FastAPI-powered remote interface.
- **Messaging:** Direct integration with **WhatsApp** and **Telegram** bot adapters.
- **Secure Remote Access:** Built-in **Cloudflare Tunnel** support for exposing the dashboard to a public URL without port forwarding.
- **Standalone GUI:** Ultra-low latency native Python interface (Tkinter).

---

## 🧩 The Module Framework

The power of ASIMOD comes from its **Module Independence**. You can create specialized tools that the Agent discovers and uses dynamically.

### Core Modular Features:
- **Dynamic Discovery:** The core automatically scans the `modules/` folder and injects module capabilities into the Agent's prompt.
- **Frontends Mounting:** Add a `web/` folder to your module, and it will be served automatically on the dashboard.
- **Lifecycle Management:** Dedicated `on_activate` and `on_deactivate` hooks for complex state management.

### Minimal Developer Boilerplate:
```python
from core.base_module import BaseModule

class MyTool(BaseModule):
    def __init__(self, chat_service, config, style, data_service=None):
        super().__init__(chat_service, config, style, data_service)
        self.name = "My Smart Tool"
        self.id = "smart_tool"
        self.icon = "🔧"

    def get_voice_commands(self):
        # Maps user intent to logic slugs (shared with the Agent)
        return {"activate engine": "run_logic"}

    def on_voice_command(self, action_slug, text):
        if action_slug == "run_logic":
            # Your custom logic here
            print("Action executed!")
```

---

## 🎨 Personalization & UX

- **Theme System:** Fully customizable aesthetics (Tokens, Fonts, Colors). Includes presets like `Midnight Purple` and `Dark Carbon`.
- **Command Dictionary:** A robust set of pre-mapped voice triggers for games, investigations, and system control.
- **Persistent Memory:** Infinite conversation threads with unique portraits, personalities, and histories.

---

## 🖥️ Execution Modes

- **Local UI:** `python main_standalone.py`
- **Headless Server:** `python main_headless.py`
- **Remote Hub:** `start_web_remote.bat`
- **Public URL:** `start_remote_public.bat`

---

Developed with ❤️ for the **ASIMOD Ecosystem**.
