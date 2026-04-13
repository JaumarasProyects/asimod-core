# ASIMOD Core: Universal Agentic Orchestrator 🤖🌌

> **Core Philosophy:** ASIMOD Core is a **general-purpose agentic system**. Its functionality is not hardcoded into the core; instead, it depends entirely on the **pluggable modules** that the user chooses to integrate. These modules are independent and provide the custom, specific functionality that the end-user requires, transforming a generic "brain" into a specialized tool.

---

## 🧠 The Concept: Brain vs. Soul

ASIMOD (Advanced Sensory Integrated Multimodal Orchestrating Device) is designed as a **Universal Orchestrator**. 

- **The Core (The Brain):** Provides the fundamental infrastructure for multimodal interaction (Vision, Audio, Memory, API). It is an "empty" orchestrator that knows how to communicate but doesn't have a specific purpose.
- **The Modules (The Soul):** Independent plugins that define the system's actual utility. Whether it's managing health, generating media, or controlling a robotic arm, the functionality lives in the modules.

---

## 🧩 The Module Ecosystem (Developer's Guide)

Modules in ASIMOD are fully decoupled. You can add, remove, or swap modules without touching the core code. 

### 🏗️ Integration Mechanics: How they connect
The program performs a dynamic scan of the `modules/` directory at startup. If it find a folder with a valid class inheriting from `BaseModule`, it becomes part of the system's ecosystem immediately.

- **Logic Integration:** The core imports your class and registers its methods.
- **UI Integration (Local):** The core calls `get_widget()` to display your custom interface in the Standalone GUI.
- **UI Integration (Remote):** If your module has a `web/` folder, the API server automatically mounts it at `/v1/modules/{module_id}/assets/` for the Dashboard.
- **Resource Integration:** Any folder named `output/` inside your module will also be served as static assets.

### 🤖 Creating Your First Module
1. **Create the Folder:** Go to the `modules/` directory and create a new folder (e.g., `my_custom_tool/`).
2. **Create the Entry Point:** Create an `__init__.py` inside that folder.
3. **Inherit from `BaseModule`:** Define your class and provide it with a unique ID and Name.

### 🎤 Commands & Agentic Intelligence
This is the most critical part of a module. By defining commands, you provide the Agent with its "Soul":

- **Voice Commands:** Traditional trigger phrases (e.g., "activate lights").
- **Agentic Orders:** The Core reads your command list and injects it into the LLM's prompt. The Agent "discovers" that your module exists and understands what actions it can perform on your behalf.

### 💻 Minimal Boilerplate Module
```python
import tkinter as tk
from core.base_module import BaseModule

class MyToolModule(BaseModule):
    def __init__(self, chat_service, config, style, data_service=None):
        super().__init__(chat_service, config, style, data_service)
        self.name = "My Smart Tool"
        self.id = "smart_tool"
        self.icon = "🔧"

    def get_widget(self, parent):
        # Your custom Tkinter UI
        frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        tk.Label(frame, text="Smart Control Panel", fg="white", bg="black").pack()
        return frame

    def get_voice_commands(self):
        # These are SHARED with the Agent reasoning engine
        return {
            "turn on engine": "start_logic",
            "set frequency": "adjust_freq"
        }

    def on_voice_command(self, action_slug, text):
        # Implementation of your modular logic
        if action_slug == "start_logic":
            print("Modular logic executed!")
```

---

## 🚀 Key Systems

### 🧠 Agentic Reasoning (The "Brain")
Unlike static bots, ASIMOD uses an **Agentic Mode** to:
- Analyze user intent via LLM.
- Search for the appropriate module in the loaded ecosystem.
- Trigger module-specific actions via JSON-structured reasoning based on the `get_voice_commands` metadata.

### 👁️ Sensory Integration (The "Inputs")
The Core provides these sensors to the Agent:
- **Vision:** Real-time analysis of webcam, screen, or files.
- **Audio:** High-fidelity STT and dual-mode TTS (Interrupt/Wait).
- **Memory:** Threaded, persistent context that grows with the user.

---

## 🖥️ Execution & Control

ASIMOD offers multiple ways to interact with its agentic core:
- **Standalone GUI:** Local Python application (Tkinter).
- **Web Dashboard:** Remote management via FastAPI.
- **Public Tunnels:** Secure remote access via Cloudflare.

---

Developed with ❤️ for the **ASIMOD Ecosystem**.
