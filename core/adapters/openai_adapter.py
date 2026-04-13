import httpx
import base64
import asyncio
from core.ports.llm_port import LLMPort

class OpenAIAdapter(LLMPort):
    """
    Adaptador para OpenAI que utiliza la API REST con soporte multimodal asíncrono.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "OpenAI"

    async def list_models(self) -> list:
        return ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o-mini"]

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def generate_chat(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        if not self.api_key:
            return "Error: No se ha configurado la API Key de OpenAI."
        
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = [{"role": "system", "content": system_prompt}] + history
            
            if images:
                for msg in reversed(messages):
                    if msg["role"] == "user":
                        orig_content = msg["content"]
                        new_content = [{"type": "text", "text": orig_content}]
                        for img_path in images:
                            try:
                                b64 = self._encode_image(img_path)
                                new_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                                })
                            except Exception as e:
                                print(f"[OpenAI] Error encoding image: {e}")
                        msg["content"] = new_content
                        break

            payload = {
                "model": model if model else "gpt-4o-mini",
                "messages": messages
            }
            
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if temperature is not None:
                payload["temperature"] = temperature

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=45.0)
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"Error OpenAI: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error de conexión con OpenAI: {str(e)}"
