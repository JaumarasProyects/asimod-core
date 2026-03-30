import requests
from core.ports.llm_port import LLMPort

class OpenAIAdapter(LLMPort):
    """
    Adaptador para OpenAI que utiliza la API REST.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "OpenAI"

    def list_models(self) -> list:
        # Lista fija para evitar peticiones excesivas en el mockup
        return ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]

    def generate_response(self, prompt: str, model: str) -> str:
        if not self.api_key:
            return "Error: No se ha configurado la OpenAI API Key."

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers, 
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"Error OpenAI: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error de conexión con OpenAI: {str(e)}"
