import requests
import base64
from core.ports.llm_port import LLMPort

class GeminiAdapter(LLMPort):
    """
    Adaptador para Google Gemini con soporte multimodal.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "Gemini"

    def list_models(self) -> list:
        return ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def generate_response(self, prompt: str, model: str, images: list = None) -> str:
        if not self.api_key:
            return "Error: No se ha configurado la Gemini API Key."

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
            
            parts = [{"text": prompt}]
            
            if images:
                for img_path in images:
                    try:
                        base64_image = self._encode_image(img_path)
                        parts.append({
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }
                        })
                    except Exception as img_err:
                        print(f"Error procesando imagen {img_path}: {img_err}")

            payload = {
                "contents": [{"parts": parts}]
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return f"Error Gemini: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error de conexión con Gemini: {str(e)}"
