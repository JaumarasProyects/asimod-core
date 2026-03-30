import json
import os

class ConfigService:
    """
    Gestiona el guardado y carga de configuraciones (API Keys, Motor por defecto).
    Persiste los datos en un archivo JSON local.
    """
    def __init__(self, filename="settings.json"):
        self.filename = filename
        self.settings = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        # Valores por defecto con todas las llaves necesarias
        return {
            "last_provider": "Ollama",
            "last_model": "llama3",
            "ollama_url": "http://localhost:11434",
            "openai_key": "",
            "gemini_key": "",
            "deepseek_key": "",
            "groq_key": "",
            "perplexity_key": "",
            "voice_provider": "Edge TTS",
            "voice_mode": "autoplay",
            "voice_save_path": "audio",
            "voice_id": "es-ES-AlvaroNeural",
            "stt_provider": "None",
            "stt_mode": "none",
            "api_port": 8000
        }

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=4)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()
