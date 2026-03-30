import requests
import json
from core.ports.llm_port import LLMPort

class OllamaAdapter(LLMPort):
    """
    Adaptador para Ollama que utiliza la API HTTP local.
    """
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    @property
    def name(self) -> str:
        return "Ollama"

    def list_models(self) -> list:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m["name"] for m in models]
        except:
            pass
        # Fallback si no hay conexión
        return ["llama3", "phi3", "mistral"]

    def generate_response(self, prompt: str, model: str) -> str:
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=30)
            if response.status_code == 200:
                return response.json().get("response", "Error: No hay respuesta.")
            return f"Error en Ollama: {response.status_code}"
        except Exception as e:
            return f"Error de conexión con Ollama: {str(e)}"
