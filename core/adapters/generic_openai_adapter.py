import requests
from core.ports.llm_port import LLMPort

class GenericOpenAIAdapter(LLMPort):
    """
    Adaptador genérico para servicios compatibles con el protocolo de OpenAI
    (DeepSeek, Groq, Perplexity, etc).
    """
    def __init__(self, name: str, api_key: str, base_url: str, models: list):
        self._name = name
        self.api_key = api_key
        self.base_url = base_url
        self._models = models

    @property
    def name(self) -> str:
        return self._name

    def list_models(self) -> list:
        return self._models

    def generate_response(self, prompt: str, model: str) -> str:
        if not self.api_key:
            return f"Error: No se ha configurado la API Key para {self._name}."

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
                f"{self.base_url}/chat/completions",
                headers=headers, 
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"Error {self._name}: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error de conexión con {self._name}: {str(e)}"
