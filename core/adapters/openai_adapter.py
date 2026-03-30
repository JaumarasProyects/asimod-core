import requests
import base64
from core.ports.llm_port import LLMPort

class OpenAIAdapter(LLMPort):
    """
    Adaptador para OpenAI que utiliza la API REST con soporte multimodal.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "OpenAI"

    def list_models(self) -> list:
        return ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def generate_response(self, prompt: str, model: str, images: list = None) -> str:
        if not self.api_key:
            return "Error: No se ha configurado la OpenAI API Key."

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Construir contenido del mensaje (texto + imágenes opcionales)
            content = [{"type": "text", "text": prompt}]
            
            if images:
                for img_path in images:
                    base64_image = self._encode_image(img_path)
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    })

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": content}]
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers, 
                json=payload,
                timeout=45
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"Error OpenAI: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error de conexión con OpenAI: {str(e)}"
