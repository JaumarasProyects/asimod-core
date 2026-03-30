import requests
from core.ports.llm_port import LLMPort

class GeminiAdapter(LLMPort):
    """
    Adaptador para Google Gemini.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "Gemini"

    def list_models(self) -> list:
        return ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]

    def generate_response(self, prompt: str, model: str) -> str:
        if not self.api_key:
            return "Error: No se ha configurado la Gemini API Key."

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return f"Error Gemini: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error de conexión con Gemini: {str(e)}"
