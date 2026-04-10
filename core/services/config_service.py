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
            "gguf_models_dir": "",
            "gguf_n_threads": 8,
            "gguf_n_ctx": 8192,
            "gguf_n_gpu_layers": 99,
            "llmstudio_url": "http://localhost:1234/v1",
            "opencode_url": "http://localhost:9090",
            "opencode_api_key": "",
            "max_tokens": 1024,
            "temperature": 0.7,
            "openai_key": "",
            "gemini_key": "",
            "deepseek_key": "",
            "groq_key": "",
            "perplexity_key": "",
            "voice_provider": "Edge TTS",
            "voice_mode": "autoplay",
            "voice_playback_mode": "interrupt",
            "voice_save_path": "audio",
            "voice_id": "es-ES-AlvaroNeural",
            "visualizer_enabled": False,
            "destreaming_enabled": False,
            "destreaming_chunk_size": 500,
            "stt_provider": "None",
            "stt_mode": "none",
            "voice_command_enabled": False,
            "voice_commands": {},
            "cloudflare_tunnel_token": "",
            "cloudflare_tunnel_id": "",
            "cloudflare_tunnel_credentials": "",
            "cloudflare_hostname": "",
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
