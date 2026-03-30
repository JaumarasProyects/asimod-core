import requests
import json

class AsimodClient:
    """
    Cliente Python para interactuar con la API de ASIMOD Core.
    """
    def __init__(self, base_url="http://localhost:8000/v1"):
        self.base_url = base_url

    def get_status(self):
        """Obtiene el estado actual del sistema."""
        try:
            response = requests.get(f"{self.base_url}/status")
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def send_chat(self, text, model=None):
        """
        Envía un mensaje al motor de chat.
        Retorna: {response, clean_text, emojis, status}
        """
        payload = {"text": text}
        if model:
            payload["model"] = model
        
        try:
            response = requests.post(f"{self.base_url}/chat", json=payload)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def list_providers(self):
        """Lista los proveedores de LLM disponibles."""
        try:
            return requests.get(f"{self.base_url}/providers").json()
        except Exception as e:
            return {"error": str(e)}

    def list_models(self, provider=None):
        """Lista los modelos del proveedor actual o de uno específico."""
        params = {"provider": provider} if provider else {}
        try:
            return requests.get(f"{self.base_url}/models", params=params).json()
        except Exception as e:
            return {"error": str(e)}

    def list_voices(self):
        """Lista las voces del motor de TTS activo."""
        try:
            return requests.get(f"{self.base_url}/voices").json()
        except Exception as e:
            return {"error": str(e)}

    def update_config(self, config_dict):
        """
        Actualiza la configuración (provider, voice_id, etc).
        Ej: client.update_config({"last_provider": "Ollama"})
        """
        try:
            response = requests.post(f"{self.base_url}/config", json=config_dict)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def stop_audio(self):
        """Detiene la reproducción de audio en el PC del Core."""
        return requests.post(f"{self.base_url}/audio/stop").json()

    def set_microphone(self, active=True):
        """Activa o desactiva la escucha remota."""
        mode = "micro" if active else "none"
        return self.update_config({"stt_mode": mode})

# --- EJEMPLO DE USO ---
if __name__ == "__main__":
    client = AsimodClient()
    
    print("--- Consultando Estado ---")
    print(client.get_status())
    
    print("\n--- Enviando Mensaje ---")
    res = client.send_chat("Hola, ¿qué puedes ver?")
    if "response" in res:
        print(f"IA: {res['response']}")
        print(f"Emojis: {res['emojis']}")
    else:
        print(f"Error: {res}")
