import requests
import json
from core.ports.llm_port import LLMPort

class OllamaAdapter(LLMPort):
    """
    Adaptador para Ollama que utiliza la API HTTP local.
    """
    def __init__(self, base_url="http://localhost:11434"):
        # Normalizar: Si el usuario puso /api al final, lo quitamos ya que 
        # los métodos lo añaden automáticamente (evitar /api/api/tags)
        if base_url.endswith("/api"):
            self.base_url = base_url[:-4]
        elif base_url.endswith("/api/"):
            self.base_url = base_url[:-5]
        else:
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
        # Si no hay conexión o falla la respuesta, devolvemos lista vacía para no engañar al usuario
        return []

    def generate_chat(self, history: list, system_prompt: str, model: str, images: list = None) -> str:
        """
        Envía un historial completo a Ollama usando el endpoint /api/chat.
        """
        try:
            # Construir la lista de mensajes completa
            messages = [{"role": "system", "content": system_prompt}] + history
            
            # Formatear adecuadamente para Ollama /api/chat
            payload = {
                "model": model,
                "messages": messages,
                "stream": False
            }
            
            # Nota: Ollama /api/chat soporta imágenes dentro del objeto del mensaje actual
            # Pero para simplicidad en este adaptador genérico, las incluimos en el último mensaje
            if images and len(messages) > 0:
                messages[-1]["images"] = images

            response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=300)
            
            if response.status_code == 200:
                return response.json().get("message", {}).get("content", "Error: No hay contenido.")
            
            if response.status_code == 404:
                return f"Error 404 en Ollama: El modelo '{model}' no está instalado."
            
            return f"Error en Ollama: {response.status_code} - {response.text}"
            
        except Exception as e:
            return f"Error de conexión con Ollama: {str(e)}"
