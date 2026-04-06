import requests
from typing import List
from core.ports.llm_port import LLMPort

class AnthropicAdapter(LLMPort):
    """
    Adaptador para Anthropic (Claude) que utiliza la API de Messages.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "Anthropic"

    def list_models(self) -> List[str]:
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229"
        ]

    def generate_chat(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        if not self.api_key:
            return "Error: No se ha configurado la API Key de Anthropic."
        
        try:
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            max_tokens_val = max_tokens if max_tokens is not None else 4096
            
            payload = {
                "model": model if model else "claude-3-5-sonnet-20241022",
                "max_tokens": max_tokens_val,
                "system": system_prompt,
                "messages": history
            }

            if temperature is not None:
                payload["temperature"] = temperature
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json()["content"][0]["text"]
            else:
                return f"Error Anthropic {response.status_code}: {response.text}"
                
        except Exception as e:
            return f"Error de conexión con Anthropic: {str(e)}"
